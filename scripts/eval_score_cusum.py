"""CUSUM on model scores (not raw streams): Bin Shams pattern.

Window model absorbs normal evolution; CUSUM integrates persistent
weak signals across windows. v7 proba cached to /tmp/v7_oof2.parquet.
"""

import glob

import numpy as np
import pandas as pd


def main():
    import joblib

    from src.cusum_bank import TabularCUSUM
    from src.window_dataset import apply_norm, build_windows, fit_clean_norm

    try:
        oof = pd.read_parquet("/tmp/v7_oof2.parquet")
        X = y = groups = starts = None
    except FileNotFoundError:
        paths = sorted(glob.glob("artifacts/m0b_mass_*.parquet"))
        df = pd.concat([pd.read_parquet(p) for p in paths], ignore_index=True)
        X, y, _, groups, starts, _ = build_windows(
            df, w=128, stride=8, invariant=True, build_jobs=4,
            return_starts=True, return_roots=True,
        )
        art = joblib.load("artifacts/window-gbm-w128-v7/model.joblib")
        model, med, iqr = art["model"], np.array(art["norm_median"]), np.array(art["norm_iqr"])
        p = model.predict_proba(apply_norm(X, med, iqr, 15))[:, 1]
        oof = pd.DataFrame({"ep": groups, "start": starts, "p": p, "y": y})
        oof.to_parquet("/tmp/v7_oof2.parquet", index=False)
    for k, h in ((0.1, 2.0), (0.2, 3.0), (0.05, 2.0)):
        hits, n, cf, cn, errs = 0, 0, 0, 0, []
        for ep, g in oof.groupby("ep"):
            g = g.sort_values("start")
            yt = g["y"].to_numpy()
            if yt.max() == 0:
                cn += 1
                c = TabularCUSUM(k=k, h=h, mu0=0.0, sigma0=1.0)
                base = g["p"].to_numpy()[:3].mean()
                if any(c.step(max(0.0, v - base)) for v in g["p"].to_numpy()):
                    cf += 1
                continue
            n += 1
            c = TabularCUSUM(k=k, h=h, mu0=0.0, sigma0=1.0)
            base = g["p"].to_numpy()[:3].mean()
            t = None
            for i, v in enumerate(g["p"].to_numpy()):
                if c.step(max(0.0, v - base)):
                    t = int(g["start"].iloc[i])
                    break
            if t is not None:
                hits += 1
                errs.append(abs(t - int(g[g["y"] == 1]["start"].min())))
        errs = np.array(errs)
        print(f"k={k} h={h}: retrieval={hits/max(1,n):.3f} "
              f"clean-fire={cf/max(1,cn):.3f} "
              f"med-err={float(np.median(errs)) if len(errs) else -1:.1f} "
              f"(MEASURED, n={n}/{cn})")


if __name__ == "__main__":
    main()
