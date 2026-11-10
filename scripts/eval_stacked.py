"""Stacked eval: LambdaRank over window-posterior aggregates (Head-A stage 2)."""

import numpy as np
import pandas as pd


def _direction_feats(onsets, ep, machines):
    """Onset/state features per machine: mirrors diagnose._eweight + flags."""
    g = onsets[onsets["ep"] == ep] if onsets is not None else None
    out = {}
    for m in machines:
        if g is None or m not in set(g["machine"]):
            out[m] = (0.0, 0.0, 0.0, 1.0)
            continue
        r = g[g["machine"] == m].iloc[0]
        kind, st = str(r["onset_kind"]), str(r["own_state"])
        if kind == "state" and st == "DOWN":
            w = 1.0
        elif st == "STARVED" and kind != "counter":
            w = 0.1
        elif kind in ("state", "counter", "oracle"):
            w = 0.6
        else:
            w = 0.3
        out[m] = (w, 1.0 if st == "DOWN" else 0.0,
                  1.0 if st == "STARVED" else 0.0, 0.0)
    # onset-order rank normalized (earliest = 1)
    if g is not None and len(g):
        om = {m: float(g[g["machine"] == m]["onset"].min()) for m in machines if m in set(g["machine"])}
        if om:
            t0, t1 = min(om.values()), max(om.values())
            for m, t in om.items():
                w, d, s, _ = out[m]
                out[m] = (w, d, s, 1.0 - (t - t0) / max(1.0, t1 - t0))
    return out


def build_rows(oof: pd.DataFrame, machines: list[str], fired: pd.Series | None = None, onsets=None):
    """Multi-signal rows: vote aggregates + sentinel-agreement (additive).

    fired: optional boolean Series aligned to oof rows (sentinel fired).
    Never filters rows — agreement is a feature, not a mask (masking
    killed top-1 0.455 -> 0.377 MEASURED).
    """
    pcols = {m: f"proba_{m}" for m in machines if f"proba_{m}" in oof.columns}
    use_proba = len(pcols) == len(machines)
    has_fired = fired is not None
    rows, y, groups, fam = [], [], [], []
    for ep, g in oof.groupby("ep"):
        truth = g[g["y"] == 1]
        if truth.empty:
            continue
        troot = str(truth["root"].mode().iloc[0])
        if troot == "none":
            continue
        family = str(truth["fam"].mode().iloc[0])
        dfeat = _direction_feats(onsets, ep, machines) if onsets is not None else None
        pm = g[g["pred"] != "none"]
        f = fired.loc[g.index].to_numpy(bool) if has_fired else None
        shares, mx, fshare, agree = {}, {}, {}, {}
        for m in machines:
            if use_proba:
                s = g[pcols[m]].to_numpy(float)
                shares[m] = float(s.mean())
                mx[m] = float(s.max())
            else:
                s = (pm["pred"] == m)
                shares[m] = float(s.mean()) if len(pm) else 0.0
                mx[m] = float(s.max()) if len(s) else 0.0
            if f is not None:
                pm_m = (g["pred"].to_numpy(dtype=str) == m)
                fshare[m] = float((f & pm_m).sum() / max(1, int(f.sum())))
                agree[m] = float((f & pm_m).sum() / max(1, int(pm_m.sum())))
            else:
                fshare[m] = 0.0
                agree[m] = 0.0
        order = sorted(machines, key=lambda m: -shares[m])
        rank = {m: i + 1 for i, m in enumerate(order)}
        vals = np.array([shares[m] for m in machines])
        mu, sd = vals.mean(), max(vals.std(), 1e-9)
        top1 = vals.max()
        srt = np.sort(vals)
        top2 = srt[-2] if len(srt) > 1 else 0.0
        for m in machines:
            onehot = [1.0 if m == x else 0.0 for x in machines]
            extra = list(dfeat[m]) if dfeat is not None else [0.0, 0.0, 0.0, 0.0]
            rows.append(
                [shares[m], mx[m], float(rank[m]), (shares[m] - mu) / sd,
                 top1 - shares[m], top2 - shares[m] if shares[m] < top1 else top1 - top2,
                 fshare[m], agree[m]]
                + extra + onehot
            )
            y.append(1 if m == troot else 0)
            groups.append(ep)
            fam.append(family)
    return np.array(rows), np.array(y), np.array(groups), np.array(fam)


def load_onsets(path: str = "artifacts/onsets.parquet"):
    """Load cached per-episode onsets; None if missing (features off)."""
    try:
        return pd.read_parquet(path)
    except FileNotFoundError:
        return None


def main():
    import lightgbm as lgb
    from sklearn.model_selection import StratifiedGroupKFold

    from src.twin import _MACHINE_ORDER

    oof = pd.read_parquet("artifacts/oof_identity.parquet")
    machines = list(_MACHINE_ORDER)
    try:
        frz = pd.read_parquet("artifacts/frozen_oof.parquet")
        foof = oof.sort_values(["ep"])
        ffrz = frz.sort_values(["ep", "start"])
        fired = None
        if (foof.groupby("ep").size() == ffrz.groupby("ep").size()).all():
            fired = pd.Series((ffrz["p"].to_numpy() >= 0.6), index=foof.index)
            print("sentinel-agreement features ON", flush=True)
        else:
            print("grid mismatch: sentinel features off", flush=True)
    except FileNotFoundError:
        fired = None
        print("no sentinel OOF: sentinel features off", flush=True)
    onsets = load_onsets()
    print(f"onset features {'ON' if onsets is not None else 'OFF'}", flush=True)
    X, y, groups, fam = build_rows(oof, machines, fired, onsets)
    famids = np.array([hash(f) % (2**31) for f in fam])
    oof_pred = np.zeros(len(y))
    cv = StratifiedGroupKFold(n_splits=3)
    for tr, te in cv.split(X, famids, groups):
        order_tr = np.argsort(groups[tr], kind="stable")
        order_te = np.argsort(groups[te], kind="stable")
        _, gtr = np.unique(groups[tr][order_tr], return_counts=True)
        _, gte = np.unique(groups[te][order_te], return_counts=True)
        dtr = lgb.Dataset(X[tr][order_tr], label=y[tr][order_tr],
                          group=[int(v) for v in gtr])
        dte = lgb.Dataset(X[te][order_te], label=y[te][order_te],
                          group=[int(v) for v in gte])
        bst = lgb.train(
            {"objective": "lambdarank", "lambdarank_truncation_level": 5,
             "lambdarank_norm": True, "num_leaves": 7, "min_data_in_leaf": 20,
             "learning_rate": 0.05, "verbose": -1},
            dtr, num_boost_round=200, valid_sets=[dte],
            callbacks=[lgb.early_stopping(20, verbose=False)],
        )
        te_idx = np.asarray(te)[order_te]
        oof_pred[te_idx] = bst.predict(X[te][order_te])
    import pandas as _pd

    _oof = _pd.read_parquet("artifacts/oof_identity.parquet")
    _votable = set()
    for ep, g in _oof.groupby("ep"):
        if (g["pred"] != "none").any():
            _votable.add(ep)
    hits, n, rrs = 0, 0, []
    vhits, vn = 0, 0
    for ep in np.unique(groups):
        m = groups == ep
        s = oof_pred[m]
        order = np.argsort(-s)
        hits += int(order[0] == int(np.argmax(y[m])))
        n += 1
        if ep in _votable:
            vhits += int(order[0] == int(np.argmax(y[m])))
            vn += 1
        rrs.append(1.0 / (int(np.where(order == int(np.argmax(y[m])))[0][0]) + 1))
    print(f"stacked episode top1={hits/max(1,n):.3f} (MEASURED, n={n})")
    print(f"  MRR={float(np.mean(rrs)):.3f} (MEASURED)")
    print(f"  votable-only top1={vhits/max(1,vn):.3f} (MEASURED, n={vn})")
    # Stage-1 baseline on IDENTICAL episodes: argmax vote-share == majority vote.
    _machines = list(__import__("src.twin", fromlist=["_MACHINE_ORDER"])._MACHINE_ORDER)
    base_hits, base_n = 0, 0
    for ep, g in _oof.groupby("ep"):
        truth = g[g["y"] == 1]
        if truth.empty or str(truth["root"].mode().iloc[0]) == "none":
            continue
        troot = str(truth["root"].mode().iloc[0])
        pm = g[g["pred"] != "none"]
        if len(pm) == 0:
            continue
        counts = pm["pred"].value_counts()
        if counts.idxmax() == troot:
            base_hits += 1
        base_n += 1
    print(f"stage-1 majority-vote top1={base_hits/max(1,base_n):.3f} (MEASURED, n={base_n})")


if __name__ == "__main__":
    main()
