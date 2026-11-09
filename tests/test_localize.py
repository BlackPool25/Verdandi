"""Localizer tests on synthetic onsets (known ground truth)."""

from __future__ import annotations

import numpy as np


def test_counter_edge_finds_run_start_at_onset():
    from src.localize import counter_edge

    c = np.zeros(200)
    c[150:] = np.arange(1, 51)  # stall run starts exactly at 150
    assert counter_edge(c, trigger=160) == 150
    assert counter_edge(np.zeros(200), trigger=100) is None


def test_cusum_backtrack_finds_abrupt_shift_near_onset():
    import numpy as np

    from src.localize import cusum_backtrack

    rng = np.random.default_rng(0)
    r = np.concatenate([rng.normal(0, 1, 150), rng.normal(3, 1, 50)])
    est = cusum_backtrack(r, trigger=170, k=1.0)
    assert est is not None and abs(est - 150) <= 6


def test_eval_one_is_deterministic(tmp_path):
    import numpy as np
    import pandas as pd

    from scripts.evaluate_localize import _eval_one

    n = 200
    g = pd.DataFrame(
        {"cycle_lag": [0] * 100 + list(range(100)), "stale_hold_run": [0] * n,
         "down_run": [0] * n,
         **{f"obs_A{i}": np.zeros(n) for i in range(3)}}
    )
    ow = pd.DataFrame({"score": np.linspace(0, 1, 9)})
    r = {"class": "delay", "t0": 100}
    a = _eval_one(1, g, ow, r, ["obs_A0", "obs_A1", "obs_A2"])
    b = _eval_one(1, g, ow, r, ["obs_A0", "obs_A1", "obs_A2"])
    assert a == b


def test_ewma_finds_gradual_ramp():
    from src.localize import ewma_onset

    rng = np.random.default_rng(1)
    r = np.concatenate([rng.normal(0, 1, 150), np.linspace(0, 6, 50)])
    est = ewma_onset(r, trigger=175)
    assert est is not None and 140 <= est <= 185
