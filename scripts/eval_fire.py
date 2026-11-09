"""Binary firing head: window fault-vs-clean, episode fire = max window score."""

import glob

import numpy as np
import pandas as pd


def main():
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.model_selection import GroupKFold

    from src.window_dataset import apply_norm, build_windows, fit_clean_norm

    paths = sorted(glob.glob("artifacts/m0b_mass_*.parquet"))
    df = pd.concat([pd.read_parquet(p) for p in paths], ignore_index=True)
    X, y, _, groups, starts, _ = build_windows(
        df, w=128, stride=8, invariant=True, build_jobs=4,
        return_starts=True, return_roots=True,
    )
    n_obs = 15
    oof = np.zeros(len(X))
    cv = GroupKFold(n_splits=3)
    for tr, te in cv.split(X, y, groups):
        med, iqr = fit_clean_norm(X[tr], (y[tr] == 0).astype(int), n_obs)
        clf = HistGradientBoostingClassifier(max_iter=200, random_state=0)
        clf.fit(apply_norm(X[tr], med, iqr, n_obs), y[tr])
        oof[te] = clf.predict_proba(apply_norm(X[te], med, iqr, n_obs))[:, 1]
    # episode retrieval vs threshold + first-fire onset
    df_oof = pd.DataFrame({"ep": groups, "start": starts, "p": oof, "y": y})
    truth = df_oof.groupby("ep")["y"].max()


    def confirmed(g: pd.DataFrame, thr: float, m: int = 2, n: int = 3):
        g = g.sort_values("start")
        hot = (g["p"].to_numpy() >= thr).astype(int)
        for i in range(len(hot)):
            if hot[max(0, i - n + 1) : i + 1].sum() >= m:
                return int(g["start"].iloc[i])
        return None

    for thr in (0.3, 0.5, 0.7):
        fired, errs, clean_fire, n_clean = {}, [], 0, 0
        for ep, g in df_oof.groupby("ep"):
            t = confirmed(g, thr)
            if truth[ep] == 0:
                n_clean += 1
                clean_fire += t is not None
                continue
            if t is None:
                continue
            fired[ep] = t
        eps = truth[truth == 1].index
        ret = len(fired) / max(1, len(eps))
        for ep, t in fired.items():
            t0 = int(df_oof[(df_oof["ep"] == ep) & (df_oof["y"] == 1)]["start"].min())
            errs.append(abs(t - t0))
        errs = np.array(errs)
        print(f"thr={thr}: confirmed-retrieval={ret:.3f} "
              f"clean-fire={clean_fire/max(1,n_clean):.3f} (n_clean={n_clean}) "
              f"med-err={float(np.median(errs)) if len(errs) else -1:.1f} "
              f"p90={float(np.percentile(errs,90)) if len(errs) else -1:.1f} "
              f"(MEASURED, n={len(eps)})")


if __name__ == "__main__":
    main()
