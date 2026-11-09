"""Battery eval: open-set LambdaRank over 26 candidates/episode (frozen T=300)."""

import glob

import numpy as np
import pandas as pd


def build_candidates(df: pd.DataFrame):
    from src.twin import _MACHINE_ORDER

    machines = [m for m in _MACHINE_ORDER]
    obs = [f"obs_{m}" for m in machines if f"obs_{m}" in df.columns]
    machines = [c[4:] for c in obs]
    rows, labels, groups, coord, fam = [], [], [], [], []
    for ep, g in df.groupby("episode_id"):
        truth = g[g["root_id"] != "none"]
        if truth.empty:
            continue
        root = str(truth["root_id"].mode().iloc[0])
        family = str(truth["fault_family"].mode().iloc[0])
        cp = str(truth["sensor_vs_process"].mode().iloc[0]) if "sensor_vs_process" in g else "?"
        nominal = g[g["fault_mask"] == 0] if "fault_mask" in g else g.head(30)
        fw = g[g["root_id"] != "none"]
        devs = {}
        for m in machines:
            c = f"obs_{m}"
            v = fw[c].to_numpy(float)
            b = nominal[c].to_numpy(float)
            mu, sd = float(b.mean()), max(float(b.std()), 1e-9)
            devs[m] = float(np.abs(v - mu).max() / sd)
        order = sorted(devs, key=devs.get, reverse=True)
        rank = {m: i + 1 for i, m in enumerate(order)}
        vals = np.array([devs[m] for m in machines])
        mu_v, sd_v = vals.mean(), max(vals.std(), 1e-9)
        for m in machines:
            onehot = [1.0 if m == x else 0.0 for x in machines]
            rows.append(
                [devs[m], float(rank[m]), (devs[m] - mu_v) / sd_v,
                 1.0 if m == root else 0.0] + onehot + [family]
            )
            labels.append(1 if m == root else 0)
            groups.append(ep)
            coord.append(cp if m == root else "?")
            fam.append(family)
    return rows, np.array(labels), np.array(groups), coord, fam, machines


def main():
    import lightgbm as lgb
    from sklearn.model_selection import StratifiedGroupKFold

    paths = sorted(glob.glob("artifacts/m0b_mass_*.parquet"))
    df = pd.concat([pd.read_parquet(p) for p in paths], ignore_index=True)
    rows, y, groups, coord, fam, machines = build_candidates(df)
    # Order-safe grouping: sort rows by episode so group counts match row order.
    order = np.argsort(np.asarray(groups), kind="stable")
    rows = [rows[i] for i in order]
    y = np.asarray(y)[order]
    groups = np.asarray(groups)[order]
    coord = [coord[i] for i in order]
    fam = np.asarray(fam)[order]
    # Harness asserts (axis-4 F1/F6): rows grouped by query, int 0/1, 1 positive/query.
    gids = np.asarray(groups)
    seen: dict = {}
    for i, g in enumerate(gids):
        if g in seen and seen[g] != i - 1 and gids[i - 1] != g:
            # non-contiguous episode block -> group/count mismatch downstream
            raise AssertionError(f"rows not grouped by episode at index {i}")
        seen[g] = i
    for e in np.unique(gids):
        m = gids == e
        assert set(np.unique(np.asarray(y)[m]).tolist()) <= {0, 1}
        assert int(np.asarray(y)[m].sum()) == 1, f"episode {e} positives != 1"
    fam_arr = np.array(fam)
    famids = np.array([hash(f) % (2**31) for f in fam_arr])
    Xnum = np.array([[r[0], r[1], r[2]] for r in rows])
    mid = np.array([[r[4 + i] for i in range(len(machines))] for r in rows])
    X = np.hstack([Xnum, mid])
    oof = np.zeros(len(y))
    cv = StratifiedGroupKFold(n_splits=3)
    for tr, te in cv.split(X, famids, groups):
        tr_ep = groups[tr]
        _, gtr = np.unique(tr_ep, return_counts=True)
        dtr = lgb.Dataset(X[tr], label=y[tr], group=[int(v) for v in gtr])
        te_ep = groups[te]
        _, gte = np.unique(te_ep, return_counts=True)
        dte = lgb.Dataset(X[te], label=y[te], group=[int(v) for v in gte])
        bst = lgb.train(
            {"objective": "lambdarank", "lambdarank_truncation_level": 5,
             "lambdarank_norm": True, "num_leaves": 7, "min_data_in_leaf": 5,
             "verbose": -1},
            dtr, num_boost_round=100, valid_sets=[dte],
            callbacks=[lgb.early_stopping(20, verbose=False)],
        )
        oof[te] = bst.predict(X[te])
    # episode top-1 from OOF scores
    hits, n, sens_h, sens_n, proc_h, proc_n, rrs = 0, 0, 0, 0, 0, 0, []
    for ep in np.unique(groups):
        m = groups == ep
        s = oof[m]
        order = np.argsort(-s)
        pred_root_idx = order[0]
        true_idx = int(np.argmax(y[m]))
        ep_machines = [machines[i] for i in range(len(machines))]
        hit = pred_root_idx == true_idx
        hits += hit
        n += 1
        rrs.append(1.0 / (int(np.where(order == true_idx)[0][0]) + 1))
        ep_idx = np.where(m)[0]
        c = coord[int(ep_idx[true_idx])]
        if "sensor" in str(c).lower():
            sens_h += hit
            sens_n += 1
        elif "process" in str(c).lower():
            proc_h += hit
            proc_n += 1
    print(f"ranker episode top1={hits/max(1,n):.3f} (MEASURED, n={n})")
    print(f"  sensor top1={sens_h/max(1,sens_n):.3f} n={sens_n}")
    print(f"  process top1={proc_h/max(1,proc_n):.3f} n={proc_n}")
    print(f"  MRR={float(np.mean(rrs)):.3f} (MEASURED)")


if __name__ == "__main__":
    main()
