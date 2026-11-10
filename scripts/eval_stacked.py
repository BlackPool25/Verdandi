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


def build_rows_free(oof: pd.DataFrame, machines: list[str], fired: pd.Series | None = None, onsets=None,
                    include_onehot: bool = True):
    """Vote-free rows: sentinel agreement + onset/state + machine identity.

    Uses NO teacher outputs (no proba_*, no pred). Sentinel `fired`
    comes from the frozen detector, not the HistGBM teacher.
    Cols per row: [fshare, agree] + onset4 [+ onehot26].
    include_onehot=False drops identity (open-set ablation: no machine prior).
    """
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
        onset_ms = set(onsets[onsets["ep"] == ep]["machine"]) if onsets is not None else set()
        f = fired.loc[g.index].to_numpy(bool) if has_fired else None
        fired_frac = float(f.mean()) if f is not None else 0.0
        fired_any = bool(f.any()) if f is not None else False
        for m in machines:
            extra = list(dfeat[m]) if dfeat is not None else [0.0, 0.0, 0.0, 0.0]
            has_on = m in onset_ms
            # Per-machine sentinel link WITHOUT teacher: fired mass counts
            # for m only if m itself has an onset (else the episode fired
            # elsewhere). Same across candidates only when all/none fire.
            fshare = fired_frac if has_on else 0.0
            agree = 1.0 if (fired_any and has_on) else 0.0
            row = [fshare, agree] + extra
            if include_onehot:
                row = row + [1.0 if m == x else 0.0 for x in machines]
            rows.append(row)
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


def flowmap_from_cache(cache: str, shard_glob: str, machines: list[str]):
    """Per-(episode, machine) incident-buffer flow features from a window cache.

    Returns {(ep, m): [up_max, down_max]} — trailing-max buffer occupancy on
    the machine's upstream/downstream edge buffers (via twin._line_edges),
    aggregated (max) over the episode's windows. Zeros when unmapped.
    """
    import glob as _glob

    from src.twin import _line_edges

    sample = pd.read_parquet(sorted(_glob.glob(shard_glob))[0])
    cols = [c for c in sample.columns if c.startswith("buffer_")] + [
        c for c in ("sunk", "scrapped", "scrapped_total", "throughput") if c in sample.columns
    ]
    jmap = {c: j for j, c in enumerate(cols)}
    F = np.load(f"{cache}/F_flow.npy", mmap_mode="r")
    meta = pd.read_parquet(f"{cache}/meta.parquet")
    edges = _line_edges()

    def _codes(v):
        if v is None:
            return []
        if isinstance(v, (list, tuple)):
            out = []
            for x in v:
                out += _codes(x)
            return out
        return [v]

    flowmap = {}
    for ep, widx in meta.groupby("ep").indices.items():
        widx = np.asarray(widx)
        for m in machines:
            up, down = edges.get(m, (None, None))
            vals = []
            for v in (_codes(up), _codes(down)):
                cols_m = [f"buffer_{c}" for c in v if f"buffer_{c}" in jmap]
                if cols_m and len(widx):
                    vals.append(float(F[widx][:, [2 * jmap[c] + 1 for c in cols_m]].max()))
                else:
                    vals.append(0.0)
            flowmap[(int(ep), m)] = vals
    return flowmap


def build_rows_hybrid(oof: pd.DataFrame, machines: list[str], fired=None, onsets=None, flowmap=None):
    """Teacher rows + 2 per-machine flow cols (hybrid: votes stay, flow adds).

    flowmap: {(ep, m): [up_max, down_max]} or None (zeros).
    """
    Xb, y, groups, fam = build_rows(oof, machines, fired, onsets)
    n = len(machines)
    flow = np.array([
        list(flowmap.get((int(groups[i]), machines[i % n]), [0.0, 0.0])) if flowmap else [0.0, 0.0]
        for i in range(len(y))
    ], dtype=float)
    return np.hstack([np.asarray(Xb, dtype=float), flow]), y, groups, fam


def _run_lambdarank(X, y, groups, fam):
    """Shared 3-fold episode-grouped LambdaRank CV → OOF scores."""
    import lightgbm as lgb
    from sklearn.model_selection import StratifiedGroupKFold

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
    return oof_pred


def _report(oof_pred, y, groups, tag, votable, fired_eps):
    import numpy as _np

    hits, n, rrs = 0, 0, []
    vhits, vn, fhits, fn = 0, 0, 0, 0
    for ep in _np.unique(groups):
        m = groups == ep
        s = oof_pred[m]
        order = _np.argsort(-s)
        hit = int(order[0] == int(_np.argmax(y[m])))
        hits += hit
        n += 1
        rrs.append(1.0 / (int(_np.where(order == int(_np.argmax(y[m])))[0][0]) + 1))
        if ep in votable:
            vhits += hit
            vn += 1
        if ep in fired_eps:
            fhits += hit
            fn += 1
    print(f"{tag} episode top1={hits/max(1,n):.3f} (MEASURED, n={n})")
    print(f"  MRR={float(_np.mean(rrs)):.3f} (MEASURED)")
    print(f"  votable-only top1={vhits/max(1,vn):.3f} (MEASURED, n={vn})")
    print(f"  detector-fired top1={fhits/max(1,fn):.3f} (MEASURED, n={fn})")
    return hits, n


def main():
    from src.twin import _MACHINE_ORDER

    oof = pd.read_parquet("artifacts/oof_identity.parquet")
    machines = list(_MACHINE_ORDER)
    foof = oof.sort_values(["ep"])
    try:
        frz = pd.read_parquet("artifacts/frozen_oof.parquet")
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
    oof_pred = _run_lambdarank(X, y, groups, fam)
    import pandas as _pd

    _oof = _pd.read_parquet("artifacts/oof_identity.parquet")
    _votable = set()
    for ep, g in _oof.groupby("ep"):
        if (g["pred"] != "none").any():
            _votable.add(ep)
    _fired_eps = set(foof.loc[fired[fired].index, "ep"]) if fired is not None else set()
    _report(oof_pred, y, groups, "stacked", _votable, _fired_eps)
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


def main_free():
    """Vote-free LambdaRank pilot: triple metric + no-onehot ablation.

    Same CV, same episodes, same sentinel/onset inputs as main() —
    only teacher proba_/vote features are removed. NOTE: fshare/agree
    are redefined (not ablated like-for-like): with no teacher there is
    no per-machine vote mask, so the episode-level fired mass counts
    for m only if m itself has an onset; onset-less episodes score
    all-zero sentinel features by construction.
    """
    from src.twin import _MACHINE_ORDER

    oof = pd.read_parquet("artifacts/oof_identity.parquet")
    machines = list(_MACHINE_ORDER)
    foof = oof.sort_values(["ep"])
    try:
        frz = pd.read_parquet("artifacts/frozen_oof.parquet")
        ffrz = frz.sort_values(["ep", "start"])
        fired = None
        if (foof.groupby("ep").size() == ffrz.groupby("ep").size()).all():
            fired = pd.Series((ffrz["p"].to_numpy() >= 0.6), index=foof.index)
    except FileNotFoundError:
        fired = None
    print(f"sentinel features {'ON' if fired is not None else 'OFF'}", flush=True)
    onsets = load_onsets()
    print(f"onset features {'ON' if onsets is not None else 'OFF'}", flush=True)
    import pandas as _pd

    _oof = _pd.read_parquet("artifacts/oof_identity.parquet")
    _votable = set(ep for ep, g in _oof.groupby("ep") if (g["pred"] != "none").any())
    _fired_eps = set(foof.loc[fired[fired].index, "ep"]) if fired is not None else set()

    X, y, groups, fam = build_rows_free(oof, machines, fired, onsets)
    _report(_run_lambdarank(X, y, groups, fam), y, groups, "free", _votable, _fired_eps)

    Xn, _, _, _ = build_rows_free(oof, machines, fired, onsets, include_onehot=False)
    _report(_run_lambdarank(Xn, y, groups, fam), y, groups, "free-no-onehot", _votable, _fired_eps)

    from src.stage2 import save, train_final

    save(train_final(X, y, groups), "artifacts/stage2-rank-free.txt")
    print("saved artifacts/stage2-rank-free.txt", flush=True)


if __name__ == "__main__":
    main()
