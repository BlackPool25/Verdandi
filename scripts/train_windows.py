#!/usr/bin/env python3
"""Supervised window GBM (max-quality track): binary fault head + family head.

GroupKFold over episodes; reports window-F1 (binary), per-family recall, and
episode-hit (any positive window in a fault episode) with Wilson CIs.
"""

from __future__ import annotations

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd  # type: ignore[import-untyped]


def train_binary_gbm(X_tr: np.ndarray, y_tr: np.ndarray) -> object:
    from sklearn.ensemble import HistGradientBoostingClassifier  # type: ignore[import-untyped]

    clf = HistGradientBoostingClassifier(max_iter=300, random_state=0)
    clf.fit(X_tr, y_tr)
    return clf


def episode_hit_rate(
    window_pred: np.ndarray, groups: np.ndarray, window_fam: np.ndarray
) -> dict:
    """Per fault episode: hit iff any window predicted positive; clean FP rate."""
    hits, clean_fp = 0, 0
    n_fault, n_clean = 0, 0
    for ep in np.unique(groups):
        m = groups == ep
        is_fault = bool((window_fam[m] != "none").any())
        if is_fault:
            n_fault += 1
            hits += int(window_pred[m].any())
        else:
            n_clean += 1
            clean_fp += int(window_pred[m].any())
    return {
        "hit_rate": hits / n_fault if n_fault else 0.0,
        "clean_fp_rate": clean_fp / n_clean if n_clean else 0.0,
        "n_fault": n_fault,
        "n_clean": n_clean,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="train window GBM on mass battery")
    ap.add_argument("--parquet", default="artifacts/m0b_mass.parquet")
    ap.add_argument("--w", type=int, default=32)
    ap.add_argument("--stride", type=int, default=8)
    ap.add_argument("--splits", type=int, default=3)
    args = ap.parse_args(argv)
    from sklearn.model_selection import StratifiedGroupKFold  # type: ignore[import-untyped]

    from src.train_pipeline import compute_raw_pointwise_f1
    from src.window_dataset import build_windows

    df = pd.read_parquet(args.parquet)
    X, y, fam, groups = build_windows(df, w=args.w, stride=args.stride)
    print(f"windows={len(X)} feats={X.shape[1]} pos_rate={y.mean():.3f}")
    cv = StratifiedGroupKFold(n_splits=args.splits)
    oof = np.zeros(len(X), dtype=int)
    for tr, te in cv.split(X, y, groups):
        clf = train_binary_gbm(X[tr], y[tr])
        oof[te] = clf.predict(X[te])  # type: ignore[union-attr]
    f1 = compute_raw_pointwise_f1(y, oof)
    ep = episode_hit_rate(oof, groups, fam)
    print(
        f"window-F1={f1:.4f} episode-hit={ep['hit_rate']:.4f} clean-fp={ep['clean_fp_rate']:.4f}"
    )
    per_fam = {}
    for f in sorted(set(fam.tolist()) - {"none"}):
        m = fam == f
        per_fam[f] = round(float(oof[m].mean()), 4)
    print("per-family window recall:", per_fam)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
