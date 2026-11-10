"""Onset cache builder tests (TDD)."""

import numpy as np
import pandas as pd


def _df(n=200, seed=0):
    rng = np.random.default_rng(seed)
    return pd.DataFrame({
        "episode_id": [1] * n,
        "step": list(range(n)),
        "obs_A0": np.concatenate([rng.normal(0, 1, 100), rng.normal(0, 1, 100) + 6.0]),
        "obs_B0": rng.normal(0, 1, n),
        "state_A0": ["RUN"] * 100 + ["DOWN"] * 100,
        "state_B0": ["RUN"] * n,
    })


def test_build_onsets_shape_and_tick():
    import sys

    sys.path.insert(0, ".")
    from scripts.build_onsets import build_onsets

    out = build_onsets(_df(), ["obs_A0", "obs_B0"])
    assert set(out.columns) == {"ep", "machine", "onset", "onset_kind", "own_state"}
    a0 = out[out["machine"] == "A0"]
    assert len(a0) == 1 and abs(int(a0["onset"].iloc[0]) - 100) <= 16
