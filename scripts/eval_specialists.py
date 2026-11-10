"""Per-family expert recall@5%FAR on the frozen window cache (Task 3 v1)."""
import numpy as np
import pandas as pd
from sklearn.model_selection import GroupKFold


def main(families=("bias", "drift", "quality", "spike"), k=5, far=0.05):
    import sys

    sys.path.insert(0, ".")
    from src.specialists import expert_score, fit_family_mask
    from src.twin import _MACHINE_ORDER

    machines = list(_MACHINE_ORDER)
    X = np.load("artifacts/window_cache/X_identity.npy", mmap_mode="r")
    meta = pd.read_parquet("artifacts/window_cache/meta.parquet")
    obs_mean = X[:, [5 * i for i in range(26)]]
    fam = meta["fam"].to_numpy(dtype=str)
    ep = meta["ep"].to_numpy()
    is_clean_ep = meta.groupby("ep")["y"].transform("max").to_numpy() == 0
    for f in families:
        recs, fires, cn = [], [], 0
        gkf = GroupKFold(n_splits=3)
        yf = (fam == f).astype(int)
        for tr, te in gkf.split(obs_mean, yf, ep):
            mu0 = obs_mean[tr][is_clean_ep[tr]].mean(axis=0)
            sd0 = obs_mean[tr][is_clean_ep[tr]].std(axis=0)
            mask = fit_family_mask(obs_mean[tr][is_clean_ep[tr]],
                                   obs_mean[tr][(fam[tr] == f)], k=k)
            s_tr = expert_score(obs_mean[tr], mask, mu0, sd0)
            epmax_tr = pd.Series(s_tr).groupby(ep[tr]).max()
            clean_tr = epmax_tr[[e for e in epmax_tr.index
                                 if (fam[tr][ep[tr] == e] != f).all()]]
            thr = float(np.quantile(clean_tr, 1 - far))
            s_te = expert_score(obs_mean[te], mask, mu0, sd0)
            epmax_te = pd.Series(s_te).groupby(ep[te]).max()
            for e, v in epmax_te.items():
                truth = f in set(fam[te][ep[te] == e])
                if truth:
                    recs.append(v > thr)
                else:
                    fires.append(v > thr)
                    cn += 1
        print(f"{f}: recall@5%FAR={np.mean(recs):.3f} (n={len(recs)}) "
              f"empiricalFA={np.mean(fires):.3f} (MEASURED)", flush=True)


if __name__ == "__main__":
    main()
