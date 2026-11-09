"""End-to-end: v7-confirmed trigger -> stage-2 attribution on fired episodes."""

import glob

import numpy as np
import pandas as pd


def main():
    import joblib

    from src.window_dataset import apply_norm, build_windows, fit_clean_norm

    paths = sorted(glob.glob("artifacts/m0b_mass_*.parquet"))
    df = pd.concat([pd.read_parquet(p) for p in paths], ignore_index=True)
    X, y, _, groups, starts, _ = build_windows(
        df, w=128, stride=8, invariant=True, build_jobs=4,
        return_starts=True, return_roots=True,
    )
    import os as _os

    _cache = "/tmp/v7_oof.parquet"
    if _os.path.exists(_cache):
        _cf = pd.read_parquet(_cache)
        assert len(_cf) == len(X), "v7 cache grid mismatch"
        p = _cf["p"].to_numpy()
    else:
        art = joblib.load("artifacts/window-gbm-w128-v7/model.joblib")
        model, med, iqr = art["model"], np.array(art["norm_median"]), np.array(art["norm_iqr"])
        n_obs = int(art["n_obs_features"])
        p = model.predict_proba(apply_norm(X, med, iqr, n_obs))[:, 1]
        pd.DataFrame({"ep": groups, "start": starts, "p": p, "y": y}).to_parquet(_cache, index=False)
    frame = pd.DataFrame({"ep": groups, "start": starts, "p": p, "y": y})

    def confirmed(g, thr=0.8, m=2, n=3):
        g = g.sort_values("start")
        hot = (g["p"].to_numpy() >= thr).astype(int)
        for i in range(len(hot)):
            if hot[max(0, i - n + 1) : i + 1].sum() >= m:
                return True
        return False

    frame = pd.DataFrame({"ep": groups, "start": starts, "p": p, "y": y})
    for thr in (0.315, 0.5, 0.544, 0.8):
        conf = {ep: confirmed(g, thr) for ep, g in frame.groupby("ep")}
    truth = frame.groupby("ep")["y"].max()
    fault_eps = truth[truth == 1].index.tolist()
    clean_eps = truth[truth == 0].index.tolist()
    for thr in (0.315, 0.5, 0.544, 0.8):
        conf = {ep: confirmed(g, thr) for ep, g in frame.groupby("ep")}
        fired = [e for e in fault_eps if conf.get(e)]
        clean_fired = [e for e in clean_eps if conf.get(e)]
        print(f"thr={thr}: v7 confirmed-retrieval={len(fired)/max(1,len(fault_eps)):.3f} "
              f"clean-fire={len(clean_fired)/max(1,len(clean_eps)):.3f} "
              f"(MEASURED, n={len(fault_eps)}/{len(clean_eps)})")
    # stage-2 top-1 on 0.544-confirmed episodes (production operating point)
    oof = pd.read_parquet("/tmp/oof_clean.parquet")
    assert (oof.groupby("ep").size() == frame.groupby("ep").size()).all(), "grid misalign"
    import scripts.eval_stacked as st

    from src.twin import _MACHINE_ORDER

    X2, y2, g2, _ = st.build_rows(oof, list(_MACHINE_ORDER))
    # reuse trained-final artifact if present, else CV (kept: CV for honesty)
    import lightgbm as lgb
    from sklearn.model_selection import StratifiedGroupKFold

    fam = oof.groupby("ep")["fam"].first()
    famids = np.array([hash(fam[e]) % (2**31) for e in g2])
    oof_pred = np.zeros(len(y2))
    cv = StratifiedGroupKFold(n_splits=3)
    for tr, te in cv.split(X2, famids, g2):
        otr = np.argsort(g2[tr], kind="stable")
        ote = np.argsort(g2[te], kind="stable")
        _, gtr = np.unique(g2[tr][otr], return_counts=True)
        _, gte = np.unique(g2[te][ote], return_counts=True)
        dtr = lgb.Dataset(X2[tr][otr], label=y2[tr][otr], group=[int(v) for v in gtr])
        dte = lgb.Dataset(X2[te][ote], label=y2[te][ote], group=[int(v) for v in gte])
        bst = lgb.train(
            {"objective": "lambdarank", "lambdarank_truncation_level": 5,
             "lambdarank_norm": True, "num_leaves": 7, "min_data_in_leaf": 20,
             "learning_rate": 0.05, "verbose": -1},
            dtr, num_boost_round=200, valid_sets=[dte],
            callbacks=[lgb.early_stopping(20, verbose=False)],
        )
        te_idx = np.asarray(te)[ote]
        oof_pred[te_idx] = bst.predict(X2[te][ote])
    hits, n = 0, 0
    conf544 = {ep: confirmed(g, 0.544) for ep, g in frame.groupby("ep")}
    for ep in np.unique(g2):
        if ep not in conf544 or not conf544[ep]:
            continue
        m = g2 == ep
        s = oof_pred[m]
        hits += int(np.argmax(s) == int(np.argmax(y2[m])))
        n += 1
    print(f"e2e confirmed top1={hits/max(1,n):.3f} (MEASURED, n={n})")
    print(f"e2e pooled top1={hits/max(1,len(fault_eps)):.3f} (MEASURED)")


if __name__ == "__main__":
    main()
