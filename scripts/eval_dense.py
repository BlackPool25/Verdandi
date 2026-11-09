"""Dense retrieval eval: per-step fault scorer -> first-fire tick vs t0_step."""

import glob

import numpy as np
import pandas as pd


def main():
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.model_selection import GroupKFold

    paths = sorted(glob.glob("artifacts/m0b_mass_*.parquet"))
    feats = None
    rows = []
    for f in paths:
        d = pd.read_parquet(f)
        num = d.select_dtypes(include=[np.number]).columns.tolist()
        drop = {"episode_id", "step", "T", "cal_win", "t0_step", "hop_step",
                "code_version", "mag_sigma"}
        feats = [c for c in num if c not in drop and not c.startswith("buffer_")]
        d = d[["episode_id", "step", "t0_step"] + feats]
        rows.append(d)
    df = pd.concat(rows, ignore_index=True)
    X = df[feats].to_numpy(float)
    y = (df["t0_step"].to_numpy() >= 0).astype(int)
    groups = df["episode_id"].to_numpy()
    oof = np.zeros(len(df))
    cv = GroupKFold(n_splits=3)
    for tr, te in cv.split(X, y, groups):
        clf = HistGradientBoostingClassifier(max_iter=100, random_state=0)
        clf.fit(X[tr], y[tr])
        oof[te] = clf.predict_proba(X[te])[:, 1]
    df["p"] = oof
    # per-episode first fire (causal smooth + peak-pick thresholds)
    from src.onset_head import pick_onset, smooth_causal

    errs, fired, n = [], 0, 0
    for ep, g in df.groupby("episode_id"):
        t0s = g[g["t0_step"] >= 0]["t0_step"].to_numpy()
        if len(t0s) == 0:
            continue
        t0 = int(np.median(t0s))
        n += 1
        g = g.sort_values("step")
        s = smooth_causal(g["p"].to_numpy())
        t = pick_onset(s)
        if t < 0:
            continue
        fired += 1
        errs.append(abs(int(g["step"].iloc[min(t, len(g) - 1)]) - t0))
    errs = np.array(errs)
    print(f"dense retrieval={fired/max(1,n):.3f} (MEASURED, n={n})")
    if len(errs):
        print(f"  onset med-abs-err={float(np.median(errs)):.1f} "
              f"p90={float(np.percentile(errs,90)):.1f} (MEASURED, n={len(errs)})")


if __name__ == "__main__":
    main()
