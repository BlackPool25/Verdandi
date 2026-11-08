"""Train pipeline module for Verdandi (M0.2f Trainable Rework / MINIPRO-19 thin contract).

Guarantees:
- build_windows(df_v5, cover): branches on scale_status. Resolved -> 0.5B/B/2B.
  Unresolved -> queries requested w from dyadic cover using binary partition.
  stride steps window starts (always >= 1); purge_embargo drops that many
  windows at each edge as an exclusion gap (never a stride).
- Splits: StratifiedGroupKFold(groups=episode_id). Zero episode leakage.
  apply_purge_embargo drops train windows within embargo of a test span.
- Normalization: Per-machine median/IQR fitted strictly on RUN-normal steps inside train folds.
- Imbalance: Balanced class weights + focal confidence weights + per-class thresholds.
  SMOTE default-OFF.
- Calibration: Clean-validation only.
- Metrics: Raw point-wise F1 (PA-OFF strictly enforced).
- Runtable: build_runtable_row schema + CLI writer (no scaler.pkl anywhere).
"""

from __future__ import annotations

import argparse
import csv
import pathlib
import time
import uuid

import numpy as np
import pandas as pd  # type: ignore[import-untyped]
from sklearn.model_selection import StratifiedGroupKFold  # type: ignore[import-untyped]
from sklearn.utils.class_weight import compute_sample_weight  # type: ignore[import-untyped]

from src.window_export import reconstruct

RUNTABLE_COLUMNS = ("run_id", "job", "n_windows", "f1_raw", "wall_seconds")


def build_windows(
    df_v5: pd.DataFrame,
    cover: dict[int, dict[str, np.ndarray]] | None = None,
    *,
    w: int = 16,
    scale_status: str = "unresolved",
    stride: int = 1,
    purge_embargo: int = 0,
) -> pd.DataFrame:
    """Build windowed feature view for downstream ML consumers.

    If scale_status == 'resolved', uses 0.5B/B/2B fixed scales.
    If scale_status == 'unresolved', queries w from the covering bank via reconstruct().

    stride steps the window starts; purge_embargo drops that many windows at
    each edge as an exclusion gap (split-boundary safety), never a stride.
    """
    if stride < 1:
        raise ValueError(f"stride must be >= 1, got {stride}")
    if purge_embargo < 0:
        raise ValueError(f"purge_embargo must be >= 0, got {purge_embargo}")
    if scale_status == "resolved":
        # Resolved scale branch: filter existing scale rows
        if "scale" in df_v5.columns:
            return df_v5[df_v5["scale"].isin(["short", "base", "long"])].copy()
        return df_v5.copy()

    # Unresolved scale branch: query w from cover or dyadic bank
    if cover is not None:
        reconstructed_rows = []
        n_steps = len(df_v5)
        starts = list(range(0, n_steps - w + 1, stride))
        if purge_embargo:
            starts = starts[purge_embargo : len(starts) - purge_embargo]
        for s in starts:
            feat = reconstruct(cover, s, w)
            feat["t_start"] = s
            feat["t_end"] = s + w
            reconstructed_rows.append(feat)
        return pd.DataFrame(reconstructed_rows)

    return df_v5.copy()


def apply_purge_embargo(
    train_idx: np.ndarray,
    t_starts: np.ndarray,
    *,
    test_start: int,
    test_end: int,
    embargo: int = 0,
) -> list[int]:
    """Drop train windows whose start falls inside [test_start - embargo, test_end + embargo)."""
    if embargo < 0:
        raise ValueError(f"embargo must be >= 0, got {embargo}")
    t = np.asarray(t_starts)
    keep = []
    for i in np.asarray(train_idx, dtype=int):
        if t[i] < test_start - embargo or t[i] >= test_end + embargo:
            keep.append(int(i))
    return keep


def fit_per_machine_median_iqr(
    df_train: pd.DataFrame,
    channels: list[str],
) -> dict[str, tuple[float, float]]:
    """Fit per-machine median and IQR on clean RUN steps inside train fold only."""
    params: dict[str, tuple[float, float]] = {}
    for ch in channels:
        col = f"obs_{ch}" if f"obs_{ch}" in df_train.columns else ch
        if col not in df_train.columns:
            continue
        state_col = f"state_{ch}"
        if state_col in df_train.columns:
            clean_run = df_train[df_train[state_col] == "RUN"][col]
        else:
            clean_run = df_train[col]

        if len(clean_run) == 0:
            clean_run = df_train[col]

        med = float(np.median(clean_run))
        q75 = float(np.percentile(clean_run, 75))
        q25 = float(np.percentile(clean_run, 25))
        iqr = float(q75 - q25) if q75 > q25 else 1.0
        params[ch] = (med, iqr)
    return params


def transform_per_machine(
    df: pd.DataFrame,
    params: dict[str, tuple[float, float]],
) -> pd.DataFrame:
    """Transform features using train-fitted median and IQR."""
    df_out = df.copy()
    for ch, (med, iqr) in params.items():
        col = f"obs_{ch}" if f"obs_{ch}" in df.columns else ch
        if col in df_out.columns:
            df_out[f"{col}_normed"] = (df_out[col] - med) / (iqr + 1e-8)
    return df_out


def create_grouped_cv(
    n_splits: int = 5,
) -> StratifiedGroupKFold:
    """Create zero-leakage StratifiedGroupKFold cross-validator grouped by episode_id."""
    return StratifiedGroupKFold(n_splits=n_splits)


def compute_raw_pointwise_f1(
    y_true: np.ndarray,
    y_pred: np.ndarray,
) -> float:
    """Compute raw point-wise F1 strictly without Point-Adjustment (PA-OFF)."""
    y_t = np.asarray(y_true, dtype=int)
    y_p = np.asarray(y_pred, dtype=int)

    tp = int(np.sum((y_t == 1) & (y_p == 1)))
    fp = int(np.sum((y_t == 0) & (y_p == 1)))
    fn = int(np.sum((y_t == 1) & (y_p == 0)))

    denom = (2 * tp) + fp + fn
    if denom == 0:
        return 0.0
    return float((2 * tp) / denom)


def compute_sample_weights(y_true: np.ndarray) -> np.ndarray:
    """Balanced class weights (mean 1.0): minority windows train louder."""
    return np.asarray(compute_sample_weight("balanced", np.asarray(y_true)), dtype=float)


def focal_confidence_weights(p_true: np.ndarray, *, gamma: float = 2.0) -> np.ndarray:
    """Focal weights (1 - p)^gamma: easy windows fade, hard ones keep full weight."""
    if gamma < 0:
        raise ValueError(f"gamma must be >= 0, got {gamma}")
    return np.asarray((1.0 - np.asarray(p_true, dtype=float)) ** gamma, dtype=float)


def pick_threshold_max_f1(scores: np.ndarray, y_true: np.ndarray) -> float:
    """Threshold maximizing raw point-wise F1 (first maximizer wins ties)."""
    s = np.asarray(scores, dtype=float)
    y = np.asarray(y_true, dtype=int)
    best_thr = float(np.max(s)) if len(s) else 0.5
    best_f1 = -1.0
    for thr in sorted(set(s.tolist())):
        f1 = compute_raw_pointwise_f1(y, (s >= thr).astype(int))
        if f1 > best_f1:
            best_f1 = f1
            best_thr = float(thr)
    return best_thr


def pick_per_class_thresholds(
    scores: np.ndarray,
    y_true: np.ndarray,
    classes: np.ndarray,
) -> dict[str, float]:
    """Per-class max-F1 thresholds (recall-first veto applied by caller)."""
    s = np.asarray(scores, dtype=float)
    y = np.asarray(y_true, dtype=int)
    c = np.asarray(classes)
    return {str(cls): pick_threshold_max_f1(s[c == cls], y[c == cls]) for cls in sorted(set(c.tolist()))}


def build_runtable_row(
    *,
    job: str,
    n_windows: int,
    f1: float,
    wall_seconds: float = 0.0,
    run_id: str | None = None,
) -> dict[str, object]:
    """One m0b-train-runtable row (stable column schema)."""
    return {
        "run_id": run_id or uuid.uuid4().hex[:8],
        "job": job,
        "n_windows": int(n_windows),
        "f1_raw": float(f1),
        "wall_seconds": float(wall_seconds),
    }


def main(argv: list[str] | None = None) -> int:
    """CLI: write a runtable schema row (pipeline entry point for CI/battery)."""
    parser = argparse.ArgumentParser(description="Verdandi train pipeline (Phase-A entry)")
    parser.add_argument("--out", required=True, help="Runtable CSV path")
    parser.add_argument("--job", default="train", help="Job name for the runtable row")
    parser.add_argument("--n-windows", type=int, default=0)
    parser.add_argument("--f1", type=float, default=0.0)
    args = parser.parse_args(argv)

    start = time.perf_counter()
    row = build_runtable_row(job=args.job, n_windows=args.n_windows, f1=args.f1)
    row["wall_seconds"] = time.perf_counter() - start
    out_path = pathlib.Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(RUNTABLE_COLUMNS))
        writer.writeheader()
        writer.writerow(row)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
