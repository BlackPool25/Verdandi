#!/usr/bin/env python3
"""Per-family specialist head: multiclass GBM over window features.

One model, 8 classes (7 fault families + none). Fault verdict = predicted
class != none; family attribution comes free. Compared against the binary
head + per-family thresholds on the same OOF protocol.
"""

from __future__ import annotations

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd  # type: ignore[import-untyped]


def train_multiclass_oof(
    X: np.ndarray,
    fam: np.ndarray,
    groups: np.ndarray,
    *,
    n_splits: int = 3,
    seed: int = 0,
) -> np.ndarray:
    """OOF predicted class labels (strings), GroupKFold, fold-fit normalization."""
    from joblib import Parallel, delayed  # type: ignore[import-untyped]
    from sklearn.ensemble import HistGradientBoostingClassifier  # type: ignore[import-untyped]
    from sklearn.model_selection import StratifiedGroupKFold  # type: ignore[import-untyped]

    from src.window_dataset import OBS_STRUCT_COLS, apply_norm

    n_obs = 15  # invariant=True hardcoded above
    classes = np.array(sorted(set(fam.tolist())))
    y = np.searchsorted(classes, np.asarray(fam))
    cv = StratifiedGroupKFold(n_splits=n_splits)
    oof = np.zeros(len(X), dtype=int)

    def _fit(tr: np.ndarray, te: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        # NOTE: fold normalization centers on ALL train rows here (multiclass
        # has no clean-only arm; unsupervised experts keep their clean fit).
        med = np.median(X[tr][:, :n_obs], axis=0)
        iqr = np.maximum(
            np.quantile(X[tr][:, :n_obs], 0.75, axis=0)
            - np.quantile(X[tr][:, :n_obs], 0.25, axis=0),
            1e-9,
        )
        clf = HistGradientBoostingClassifier(max_iter=300, random_state=seed)
        clf.fit(apply_norm(X[tr], med, iqr, n_obs), y[tr])
        return te, clf.predict(apply_norm(X[te], med, iqr, n_obs))

    for te, pred in Parallel(n_jobs=-1)(
        delayed(_fit)(tr, te) for tr, te in cv.split(X, y, groups)
    ):
        oof[te] = pred
    return classes[oof]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="multiclass specialist OOF")
    ap.add_argument("--parquet", default="artifacts/m0b_mass_*.parquet")
    ap.add_argument("--w", type=int, default=128)
    ap.add_argument("--stride", type=int, default=8)
    ap.add_argument("--splits", type=int, default=3)
    ap.add_argument("--save-oof", default="")
    args = ap.parse_args(argv)
    import glob as _glob

    from src.train_pipeline import compute_raw_pointwise_f1
    from src.window_dataset import build_windows

    paths = sorted(_glob.glob(args.parquet))
    df = pd.concat([pd.read_parquet(p) for p in paths], ignore_index=True)
    X, y, fam, groups = build_windows(df, w=args.w, stride=args.stride, invariant=True)
    pred = train_multiclass_oof(X, fam, groups, n_splits=args.splits)
    dec = (pred != "none").astype(int)
    f1 = compute_raw_pointwise_f1(y, dec)
    print(f"multiclass window-F1={f1:.4f} (fault = pred != none)")
    per = {}
    for f in sorted(set(fam.tolist()) - {"none"}):
        m = (fam == f) & (y == 1)
        per[f] = round(float((pred[m] == f).mean()) if m.sum() else 0.0, 4)
    print("per-family attribution accuracy:", per)
    if args.save_oof:
        pd.DataFrame(
            {"pred": pred, "dec": dec, "y": y, "fam": fam, "ep": groups}
        ).to_parquet(args.save_oof, index=False)
        print(f"oof saved -> {args.save_oof}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
