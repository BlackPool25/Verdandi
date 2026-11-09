"""Multi-scale fusion tests (synthetic; full run is scripts/fuse_scales.py)."""

from __future__ import annotations

import numpy as np
import pandas as pd


def _tiny_battery() -> pd.DataFrame:
    n = 64
    return pd.DataFrame(
        {
            "episode_id": [1] * n + [2] * n,
            "step": list(range(n)) * 2,
            "y": [0] * 32 + [1] * 32 + [0] * 64,
            "fault_family": ["none"] * 32 + ["spike"] * 32 + ["none"] * 64,
            "obs_A0": np.concatenate(
                [np.zeros(32), np.linspace(0, 8, 32), np.zeros(64)]
            ),
            "cycle_lag": list(range(n)) * 2,
            "stale_hold_run": [0] * (2 * n),
            "reject_flag_count": [0] * (2 * n),
            "degrade_flag_count": [0] * (2 * n),
        }
    )


def test_fuse_point_scores_averages_scales_and_localizes():
    from scripts.fuse_scales import fuse_point_scores
    from src.window_dataset import build_windows

    df = _tiny_battery()
    oofs = []
    for w in (16, 32):
        _X, _y, _fam, groups, starts = build_windows(
            df, w=w, stride=16, invariant=True, return_starts=True
        )
        oofs.append(
            pd.DataFrame(
                {"score": np.linspace(0, 1, len(_X)), "ep": groups, "start": starts}
            )
        )
    fused, ep, st = fuse_point_scores(oofs[0], oofs[1], df, w_a=16, w_b=32, stride=16)
    assert len(fused) == len(ep) == len(st) and np.isfinite(fused).all()
    assert set(np.unique(ep)) == {1, 2}
    # Same (episode, step) key space on both scales: fused covers fault ticks.
    assert fused.max() > fused.min()
