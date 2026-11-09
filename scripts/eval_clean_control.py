"""Clean-episode control: false-fire rate of the dense scorer (TDD-adjacent probe)."""

import glob

import numpy as np
import pandas as pd


def main():
    from sklearn.ensemble import HistGradientBoostingClassifier

    from src.onset_head import pick_onset, smooth_causal

    feats = None
    tr = []
    for f in sorted(glob.glob("artifacts/m0b_mass_*.parquet")):
        if f.endswith("m0b_mass_00.parquet"):
            continue
        d = pd.read_parquet(f)
        if feats is None:
            feats = [c for c in d.columns
                     if c.startswith("obs_") or c.startswith("current_")]
        y = (d["root_id_step"].to_numpy(dtype=str) != "none").astype(int)
        tr.append((d[feats].to_numpy(float), y))
    Xtr = np.vstack([t[0] for t in tr])
    ytr = np.concatenate([t[1] for t in tr])
    clf = HistGradientBoostingClassifier(max_iter=100, random_state=0)
    clf.fit(Xtr, ytr)
    # clean shard: fire rate must be ~0, else the scorer is a bias artifact
    d0 = pd.read_parquet("artifacts/m0b_mass_00.parquet")
    X0 = d0[feats].to_numpy(float)
    p0 = clf.predict_proba(X0)[:, 1]
    d0 = d0.assign(p=p0)
    fired, n = 0, 0
    for ep, g in d0.groupby("episode_id"):
        n += 1
        g = g.sort_values("step")
        if pick_onset(smooth_causal(g["p"].to_numpy())) >= 0:
            fired += 1
    print(f"clean false-fire={fired/max(1,n):.3f} (MEASURED, n={n})")


if __name__ == "__main__":
    main()
