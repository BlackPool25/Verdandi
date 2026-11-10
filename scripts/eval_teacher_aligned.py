"""Teacher-aligned stage-2: rows from sentinel-fired windows only."""

import numpy as np
import pandas as pd


def main():
    import lightgbm as lgb
    from sklearn.model_selection import StratifiedGroupKFold

    from src.twin import _MACHINE_ORDER

    oof = pd.read_parquet("artifacts/oof_identity.parquet")
    frz = pd.read_parquet("artifacts/frozen_oof.parquet")
    machines = list(_MACHINE_ORDER)
    # align by (ep, within-episode order); both grids identical
    oof = oof.sort_values(["ep"]).reset_index(drop=True)
    frz = frz.sort_values(["ep", "start"]).reset_index(drop=True)
    cnt_o = oof.groupby("ep").size()
    cnt_f = frz.groupby("ep").size()
    assert ((cnt_o - cnt_f) == 0).all(), "grid mismatch"
    oof["fired"] = (frz["p"].to_numpy() >= 0.6)
    rows, y, groups, fam = [], [], [], []
    for ep, g in oof.groupby("ep"):
        truth = g[g["y"] == 1]
        if truth.empty:
            continue
        troot = str(truth["root"].mode().iloc[0])
        if troot == "none":
            continue
        family = str(truth["fam"].mode().iloc[0])
        pm = g[(g["pred"] != "none") & (g["fired"])]
        shares, mx = {}, {}
        for m in machines:
            s = (pm["pred"] == m)
            shares[m] = float(s.mean()) if len(pm) else 0.0
            mx[m] = float(s.max()) if len(s) else 0.0
        order = sorted(machines, key=lambda m: -shares[m])
        rank = {m: i + 1 for i, m in enumerate(order)}
        vals = np.array([shares[m] for m in machines])
        mu, sd = vals.mean(), max(vals.std(), 1e-9)
        top = vals.max()
        srt = np.sort(vals)
        top2 = srt[-2] if len(srt) > 1 else 0.0
        for m in machines:
            onehot = [1.0 if m == x else 0.0 for x in machines]
            rows.append(
                [shares[m], mx[m], float(rank[m]), (shares[m] - mu) / sd,
                 top - shares[m], top2 - shares[m] if shares[m] < top else top - top2]
                + onehot
            )
            y.append(1 if m == troot else 0)
            groups.append(ep)
            fam.append(family)
    X = np.array(rows)
    y = np.array(y)
    groups = np.array(groups)
    famids = np.array([hash(f) % (2**31) for f in fam])
    oof_pred = np.zeros(len(y))
    cv = StratifiedGroupKFold(n_splits=3)
    for tr, te in cv.split(X, famids, groups):
        otr = np.argsort(groups[tr], kind="stable")
        ote = np.argsort(groups[te], kind="stable")
        _, gtr = np.unique(groups[tr][otr], return_counts=True)
        _, gte = np.unique(groups[te][ote], return_counts=True)
        dtr = lgb.Dataset(X[tr][otr], label=y[tr][otr], group=[int(v) for v in gtr])
        dte = lgb.Dataset(X[te][ote], label=y[te][ote], group=[int(v) for v in gte])
        bst = lgb.train(
            {"objective": "lambdarank", "lambdarank_truncation_level": 5,
             "lambdarank_norm": True, "num_leaves": 7, "min_data_in_leaf": 20,
             "learning_rate": 0.05, "verbose": -1},
            dtr, num_boost_round=200, valid_sets=[dte],
            callbacks=[lgb.early_stopping(20, verbose=False)],
        )
        te_idx = np.asarray(te)[ote]
        oof_pred[te_idx] = bst.predict(X[te][ote])
    hits, n, rrs = 0, 0, []
    for ep in np.unique(groups):
        m = groups == ep
        s = oof_pred[m]
        order = np.argsort(-s)
        hits += int(order[0] == int(np.argmax(y[m])))
        n += 1
        rrs.append(1.0 / (int(np.where(order == int(np.argmax(y[m])))[0][0]) + 1))
    print(f"teacher-aligned top1={hits/max(1,n):.3f} (MEASURED, n={n})")
    print(f"  MRR={float(np.mean(rrs)):.3f} (MEASURED)")


if __name__ == "__main__":
    main()
