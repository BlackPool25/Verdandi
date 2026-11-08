"""GroupKFold out-of-fold scoring with fold-only normalization.

Expert protocol (numpy, larger-abnormal scores):
    scorer = maker(X_train_clean, y_train)   # fit on train NORMALS only
    scores = scorer(X_test)                   # 1-D array, larger = more abnormal
Normalization reuses train_pipeline.fit_transform_fold inside each fold, so no
fold ever sees another fold's statistics.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
import pandas as pd  # type: ignore[import-untyped]

from src.train_pipeline import create_grouped_cv, fit_transform_fold

Scorer = Callable[[np.ndarray], np.ndarray]
Maker = Callable[[np.ndarray, np.ndarray], Scorer]


def _normed_cols(df: pd.DataFrame, channels: list[str], transformed: pd.DataFrame) -> list[str]:
    cols = []
    for ch in channels:
        col = f"obs_{ch}" if f"obs_{ch}" in df.columns else ch
        normed = f"{col}_normed"
        if normed in transformed.columns:
            cols.append(normed)
    return cols


def run_oof(
    df: pd.DataFrame,
    feature_cols: list[str],
    experts: dict[str, Maker],
    *,
    n_splits: int = 5,
    group_col: str = "episode_id",
    label_col: str = "y",
) -> pd.DataFrame:
    """Score every row from a model blind to its episode (one score col per expert)."""
    y = df[label_col].to_numpy(dtype=int)
    groups = df[group_col].to_numpy()
    cv = create_grouped_cv(n_splits)
    scores = {name: np.full(len(df), np.nan) for name in experts}
    for tr, te in cv.split(np.zeros((len(df), 1)), y, groups):
        tr_t, te_t, _ = fit_transform_fold(
            df.iloc[tr], df.iloc[te], list(feature_cols)
        )
        cols = _normed_cols(df, list(feature_cols), te_t)
        x_tr = tr_t[cols].to_numpy(dtype=float)
        x_te = te_t[cols].to_numpy(dtype=float)
        y_tr = y[tr]
        for name, maker in experts.items():
            scorer = maker(x_tr[y_tr == 0], y_tr)
            scores[name][te] = np.asarray(scorer(x_te), dtype=float).ravel()
    out = df.copy()
    for name, s in scores.items():
        out[name] = s
    return out
