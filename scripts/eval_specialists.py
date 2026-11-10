"""Per-family expert recall@5%FAR on the frozen window cache (Task 3 v1)."""
import numpy as np
import pandas as pd
from sklearn.model_selection import GroupKFold


def main(families=("bias", "drift", "quality", "spike"), k=5, far=0.05, variant=1):
    import sys

    sys.path.insert(0, ".")
    from src.specialists import expert_score, fit_family_mask, trajectory_score, tune_h
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
            starts_tr = meta["start"].to_numpy()[tr]
            if variant == 1:
                epmax_tr = pd.Series(s_tr).groupby(ep[tr]).max()
                clean_tr = epmax_tr[[e for e in epmax_tr.index
                                     if (fam[tr][ep[tr] == e] != f).all()]]
                thr = float(np.quantile(clean_tr, 1 - far))
            else:
                m0, s0 = s_tr[is_clean_ep[tr]].mean(), s_tr[is_clean_ep[tr]].std()
                trajs = {}
                for e in np.unique(ep[tr]):
                    m = ep[tr] == e
                    trajs[e] = (s_tr[m][np.argsort(starts_tr[m])] - m0) / (s0 + 1e-9)
                clean_trajs = [t for e, t in trajs.items()
                               if (fam[tr][ep[tr] == e] != f).all()]
                thr = tune_h(clean_trajs, far=far)
                m0s, s0s = m0, s0
            s_te = expert_score(obs_mean[te], mask, mu0, sd0)
            starts_te = meta["start"].to_numpy()[te]
            if variant == 1:
                epmax_te = pd.Series(s_te).groupby(ep[te]).max()
                for e, v in epmax_te.items():
                    truth = f in set(fam[te][ep[te] == e])
                    if truth:
                        recs.append(v > thr)
                    else:
                        fires.append(v > thr)
                        cn += 1
            else:
                for e in np.unique(ep[te]):
                    m = ep[te] == e
                    traj = (s_te[m][np.argsort(starts_te[m])] - m0s) / (s0s + 1e-9)
                    hit = trajectory_score(traj, h=thr)
                    if f in set(fam[te][m]):
                        recs.append(bool(hit))
                    else:
                        fires.append(bool(hit))
                        cn += 1
        print(f"{f}: recall@5%FAR={np.mean(recs):.3f} (n={len(recs)}) "
              f"empiricalFA={np.mean(fires):.3f} (MEASURED)", flush=True)


if __name__ == "__main__":
    import sys

    main(variant=int(sys.argv[1]) if len(sys.argv) > 1 else 1)
