"""Step dataset builder tests (groups = episode_id, NaN rows dropped)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.step_dataset import build_step_dataset


def test_builder_aligns_and_drops_nan():
    df = pd.DataFrame(
        {"episode_id": [1, 1, 2], "y": [0, 1, 0], "a": [1.0, float("nan"), 3.0]}
    )
    X, y, groups, names = build_step_dataset(df, feature_cols=["a"])
    assert X.shape == (2, 1) and y.tolist() == [0, 0] and groups.tolist() == [1, 2]
    assert names == ["a"] and np.isfinite(X).all()
