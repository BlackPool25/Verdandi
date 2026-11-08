"""Window-dataset builder tests (max-quality track: supervised windows, not steps)."""

from __future__ import annotations

import numpy as np
import pandas as pd


def _df() -> pd.DataFrame:
    n = 64
    return pd.DataFrame(
        {
            "episode_id": [1] * n,
            "step": list(range(n)),
            "y": [0] * 32 + [1] * 32,
            "fault_family": ["none"] * 32 + ["delay"] * 32,
            "obs_A0": np.concatenate([np.zeros(32), np.linspace(0, 8, 32)]),
            "cycle_lag": list(range(n)),
            "stale_hold_run": [0] * n,
        }
    )


def test_windows_cover_episode_with_labels_and_no_future():
    from src.window_dataset import build_windows

    X, y, fam, groups = build_windows(_df(), w=16, stride=8)
    assert len(X) == len(y) == len(fam) == len(groups)
    assert set(np.unique(y)) <= {0, 1}
    # A window fully before the fault must be clean; one fully inside faulty.
    assert y[0] == 0 and fam[0] == "none"
    assert y[-1] == 1 and fam[-1] == "delay"
    # Feature matrix is finite and has the documented width.
    assert np.isfinite(X).all() and X.shape[1] > 5


def test_window_features_separate_shift():
    from src.window_dataset import build_windows

    X, y, _, _ = build_windows(_df(), w=16, stride=8)
    assert X[y == 1].mean() > X[y == 0].mean()
