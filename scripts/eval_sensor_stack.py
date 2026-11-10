"""Sensor stack eval on twin bias/drift/spike episodes (Task 4 measurement)."""
import glob

import numpy as np
import pandas as pd


def main(n_ep=60, seed=0):
    import sys

    sys.path.insert(0, ".")
    from src.sensor_stack import dpca_augment, ebf_filter, fit_pca, pdc_q, rbc_t2
    from src.twin import _MACHINE_ORDER

    machines = list(_MACHINE_ORDER)
    obs = [f"obs_{m}" for m in machines]
    paths = sorted(glob.glob("artifacts/m0b_mass_*.parquet"))
    df = pd.concat([pd.read_parquet(p) for p in paths], ignore_index=True)
    rng = np.random.default_rng(seed)
    out = {}
    for fam in ("bias", "drift", "spike"):
        eps = sorted(df.loc[(df["fault_family"] == fam) & (df["root_id"] != "none"), "episode_id"].unique())
        eps = [e for e in eps][:n_ep]
        # clean pool for PCA fit
        ceps = rng.choice(sorted(df.loc[df["family"] == "clean", "episode_id"].unique()), size=30, replace=False)
        Zc = []
        for e in ceps:
            g = df[df["episode_id"] == e].sort_values("step")
            Zc.append(dpca_augment(g[obs].to_numpy(), d=10))
        P, lam, mu, sd = fit_pca(np.vstack(Zc))
        hits = n = 0
        fa = tfa = 0
        for e in eps:
            g = df[df["episode_id"] == e].sort_values("step")
            X = dpca_augment(g[obs].to_numpy(), d=10)
            C = rbc_t2(X, P, lam, mu, sd)
            base = C.reshape(len(C), -1, len(machines)).sum(axis=1)
            am = base.argmax(axis=1)
            al = ebf_filter(am, n_vars=len(machines))
            truth = str(g["root_id"].mode().iloc[0])
            pred = machines[int(np.argmax([(am == i).sum() for i in range(len(machines))]))] if not al.any() else machines[int(np.argmax([((am == i) & al).sum() for i in range(len(machines))]))]
            hits += pred == truth
            n += 1
        # clean FA: fraction of clean eps where EBF ever alarms
        for e in ceps[:20]:
            g = df[df["episode_id"] == e].sort_values("step")
            X = dpca_augment(g[obs].to_numpy(), d=10)
            C = rbc_t2(X, P, lam, mu, sd)
            base = C.reshape(len(C), -1, len(machines)).sum(axis=1)
            if ebf_filter(base.argmax(axis=1), n_vars=len(machines)).any():
                fa += 1
            tfa += 1
        print(f"{fam}: sensor top-1={hits/max(1,n):.3f} (n={n}) clean-FA={fa/max(1,tfa):.3f} (MEASURED)", flush=True)


if __name__ == "__main__":
    main()
