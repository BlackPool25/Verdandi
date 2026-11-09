"""Firing-head clean control: fire rate on all-clean shard + threshold sweep."""

import glob

import numpy as np
import pandas as pd


def main():
    from sklearn.ensemble import HistGradientBoostingClassifier

    from src.window_dataset import apply_norm, build_windows, fit_clean_norm

    train_paths = sorted(glob.glob("artifacts/m0b_mass_*.parquet"))
    train_paths = [p for p in train_paths if not p.endswith("m0b_mass_00.parquet")]
    df = pd.concat([pd.read_parquet(p) for p in train_paths], ignore_index=True)
    X, y, _, groups, _, _ = build_windows(
        df, w=128, stride=8, invariant=True, build_jobs=4,
        return_starts=True, return_roots=True,
    )
    n_obs = 15
    med, iqr = fit_clean_norm(X, (y == 0).astype(int), n_obs)
    clf = HistGradientBoostingClassifier(max_iter=200, random_state=0)
    clf.fit(apply_norm(X, med, iqr, n_obs), y)
    d0 = pd.read_parquet("artifacts/m0b_mass_00.parquet")
    X0, _, _, g0, _, _ = build_windows(
        d0, w=128, stride=8, invariant=True, build_jobs=4,
        return_starts=True, return_roots=True,
    )
    p0 = clf.predict_proba(apply_norm(X0, med, iqr, n_obs))[:, 1]
    f0 = pd.DataFrame({"ep": g0, "p": p0})
    eps = f0["ep"].unique()
    for thr in (0.3, 0.5, 0.7):
        fired = f0[f0["p"] >= thr].groupby("ep").size()
        print(f"thr={thr}: clean false-fire={len(fired)/max(1,len(eps)):.3f} "
              f"(MEASURED, n={len(eps)})")


if __name__ == "__main__":
    main()
