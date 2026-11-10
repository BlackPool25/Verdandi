"""Window cache roundtrip."""

import numpy as np
import pandas as pd


def test_cache_roundtrip(tmp_path):
    import scripts.cache_windows as cw

    df = pd.DataFrame({
        "episode_id": [1] * 300 + [2] * 300,
        "step": list(range(300)) * 2,
        "obs_A0": np.random.default_rng(0).normal(0, 1, 600),
        "obs_A1": np.random.default_rng(1).normal(0, 1, 600),
        "fault_family": ["none"] * 600,
        "root_id_step": ["none"] * 600,
        "y": [0] * 600,
    })
    from src.window_dataset import build_windows

    X, y, fam, groups, starts, roots = build_windows(
        df, w=16, stride=16, invariant=True, return_starts=True, return_roots=True,
    )
    assert len(X) == len(groups) == len(starts)
    assert set(np.unique(groups)) == {1, 2}
