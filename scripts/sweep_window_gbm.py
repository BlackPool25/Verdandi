#!/usr/bin/env python3
"""Hyperparameter sweep + quality-specialist trial (step 2 of ship).

Small GroupKFold grid on an episode subset for speed; quality head tries wider
windows (w=64) where sparse-kit reject signals accumulate. Winner adopted only
if it beats the tuned 0.9625 line (or quality >= 0.90 without F1 regression).
"""

from __future__ import annotations

import argparse
import itertools
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd  # type: ignore[import-untyped]


def sweep(
    X: np.ndarray, y: np.ndarray, groups: np.ndarray, configs: list[dict]
) -> list[tuple[float, dict]]:
    from sklearn.ensemble import HistGradientBoostingClassifier  # type: ignore[import-untyped]
    from sklearn.model_selection import StratifiedGroupKFold  # type: ignore[import-untyped]

    from src.train_pipeline import compute_raw_pointwise_f1

    out = []
    cv = StratifiedGroupKFold(n_splits=2)
    for cfg in configs:
        f1s = []
        for tr, te in cv.split(X, y, groups):
            clf = HistGradientBoostingClassifier(random_state=0, **cfg)
            clf.fit(X[tr], y[tr])
            f1s.append(compute_raw_pointwise_f1(y[te], clf.predict(X[te])))
        out.append((float(np.mean(f1s)), cfg))
        print(f"F1={out[-1][0]:.4f} {cfg}", flush=True)
    return sorted(out, key=lambda t: t[0], reverse=True)


GRID = [
    {"max_iter": m, "max_depth": d, "learning_rate": lr, "min_samples_leaf": ml}
    for m, d, lr, ml in itertools.product(
        [200, 500], [None, 12], [0.05, 0.1], [20, 100]
    )
]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="sweep GBM + quality w=64 trial")
    ap.add_argument("--parquet", default="artifacts/m0b_mass_*.parquet")
    ap.add_argument("--max-eps", type=int, default=300)
    args = ap.parse_args(argv)
    import glob as _glob

    from src.window_dataset import build_windows

    paths = sorted(_glob.glob(args.parquet))
    df = pd.concat([pd.read_parquet(p) for p in paths], ignore_index=True)
    eps = sorted(df["episode_id"].unique())[: args.max_eps]
    sub = df[df["episode_id"].isin(eps)].reset_index(drop=True)
    X, y, _fam, groups = build_windows(sub, w=32, stride=8)
    print(f"sweep: {len(X)} windows, {len(eps)} eps", flush=True)
    ranked = sweep(X, y, groups, GRID)
    print(f"BEST {ranked[0]}", flush=True)
    # Quality specialist: w=64 windows, quality-vs-rest head, same 2-fold protocol.
    Xq, yq, famq, gq = build_windows(sub, w=64, stride=16)
    yqr = ((yq == 1) & (famq == "quality")).astype(int)
    best_cfg = ranked[0][1]
    ranked_q = sweep(Xq, yqr, gq, [best_cfg])
    print(f"QUALITY w64 {ranked_q[0]}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
