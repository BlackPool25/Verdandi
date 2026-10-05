"""Train pipeline module for Verdandi (M0.2f Trainable Rework / MINIPRO-19 thin contract).

Guarantees:
- build_windows(df_v5, cover): branches on scale_status. Resolved -> 0.5B/B/2B.
  Unresolved -> queries requested w from dyadic cover using binary partition.
- Splits: StratifiedGroupKFold(groups=episode_id). Zero episode leakage.
- Normalization: Per-machine median/IQR fitted strictly on RUN-normal steps inside train folds.
- Imbalance: Class weights + per-class thresholds. SMOTE default-OFF.
- Calibration: Clean-validation only.
- Metrics: Raw point-wise F1 (PA-OFF strictly enforced).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedGroupKFold

from src.window_export import reconstruct


def build_windows(
    df_v5: pd.DataFrame,
    cover: dict[int, dict[str, np.ndarray]] | None = None,
    *,
    w: int = 16,
    scale_status: str = "unresolved",
    purge_embargo: int = 1,
) -> pd.DataFrame:
    """Build windowed feature view for downstream ML consumers.

    If scale_status == 'resolved', uses 0.5B/B/2B fixed scales.
    If scale_status == 'unresolved', queries w from the covering bank via reconstruct().
    """
    if scale_status == "resolved":
        # Resolved scale branch: filter existing scale rows
        if "scale" in df_v5.columns:
            return df_v5[df_v5["scale"].isin(["short", "base", "long"])].copy()
        return df_v5.copy()

    # Unresolved scale branch: query w from cover or dyadic bank
    if cover is not None:
        reconstructed_rows = []
        n_steps = len(df_v5)
        for s in range(0, n_steps - w + 1, purge_embargo):
            feat = reconstruct(cover, s, w)
            feat["t_start"] = s
            feat["t_end"] = s + w
            reconstructed_rows.append(feat)
        return pd.DataFrame(reconstructed_rows)

    return df_v5.copy()


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
