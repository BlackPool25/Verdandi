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


def pick_per_family_thresholds(
    scores: np.ndarray, y_true: np.ndarray, families: np.ndarray
) -> dict[str, float]:
    """Per-family max-F1 thresholds on window scores (tuning slice = eval slice).

    Optimism caveat: thresholds picked on OOF are validation numbers, not test.
    """
    from src.train_pipeline import pick_threshold_max_f1

    s = np.asarray(scores, dtype=float)
    y = np.asarray(y_true, dtype=int)
    f = np.asarray(families)
    return {
        str(fam): float(pick_threshold_max_f1(s[f == fam], y[f == fam]))
        for fam in sorted(set(f.tolist()))
    }


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
    ap.add_argument("--parquet", default="artifacts/m0b_mass_*.parquet")
    ap.add_argument("--w", type=int, default=32)
    ap.add_argument("--stride", type=int, default=8)
    ap.add_argument("--splits", type=int, default=3)
    args = ap.parse_args(argv)
    import glob as _glob

    from sklearn.model_selection import StratifiedGroupKFold  # type: ignore[import-untyped]

    from src.train_pipeline import compute_raw_pointwise_f1
    from src.window_dataset import build_windows

    paths = sorted(_glob.glob(args.parquet))
    if not paths:
        raise SystemExit(f"no parquet shards match {args.parquet}")
    df = pd.concat([pd.read_parquet(p) for p in paths], ignore_index=True)
    X, y, fam, groups = build_windows(df, w=args.w, stride=args.stride)
    print(f"windows={len(X)} feats={X.shape[1]} pos_rate={y.mean():.3f}")
    cv = StratifiedGroupKFold(n_splits=args.splits)
    oof = np.zeros(len(X))
    for tr, te in cv.split(X, y, groups):
        clf = train_binary_gbm(X[tr], y[tr])
        oof[te] = clf.predict_proba(X[te])[:, 1]  # type: ignore[union-attr]
    f1 = compute_raw_pointwise_f1(y, (oof >= 0.5).astype(int))
    ep = episode_hit_rate((oof >= 0.5).astype(int), groups, fam)
    print(
        f"window-F1={f1:.4f} episode-hit={ep['hit_rate']:.4f} clean-fp={ep['clean_fp_rate']:.4f}"
    )
    thr = pick_per_family_thresholds(oof, y, fam)
    tuned = np.zeros(len(X), dtype=int)
    for f in sorted(set(fam.tolist())):
        m = fam == f
        tuned[m] = (oof[m] >= thr[str(f)]).astype(int)
    f1t = compute_raw_pointwise_f1(y, tuned)
    ept = episode_hit_rate(tuned, groups, fam)
    print(
        f"tuned window-F1={f1t:.4f} episode-hit={ept['hit_rate']:.4f} clean-fp={ept['clean_fp_rate']:.4f}"
    )
    per_fam = {}
    for f in sorted(set(fam.tolist()) - {"none"}):
        m = fam == f
        per_fam[f] = round(float(tuned[m].mean()), 4)
    print("per-family window recall:", per_fam)
    print("per-family thresholds:", {k: round(v, 4) for k, v in thr.items()})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
