"""Per-step ML dataset from v6 export rows (groups = episode_id)."""

from __future__ import annotations

import numpy as np
import pandas as pd  # type: ignore[import-untyped]


def build_step_dataset(
    df: pd.DataFrame,
    *,
    feature_cols: list[str],
    label_col: str = "y",
    group_col: str = "episode_id",
) -> tuple[np.ndarray, np.ndarray, np.ndarray, list[str]]:
    """X/y/groups aligned; rows with non-finite features are dropped (count logged)."""
    use = [c for c in feature_cols if c in df.columns]
    x = df[use].to_numpy(dtype=float)
    ok = np.isfinite(x).all(axis=1)
    dropped = int((~ok).sum())
    if dropped:
        print(f"build_step_dataset: dropped {dropped}/{len(df)} non-finite rows")
    return (
        x[ok],
        df[label_col].to_numpy(dtype=int)[ok],
        df[group_col].to_numpy()[ok],
        use,
    )
