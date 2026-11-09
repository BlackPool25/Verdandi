"""Lag-flow tests: pre-whitened lag-scan pairwise flow (walk edge weights)."""

import numpy as np


def _pair(n=300, lag=6, seed=0):
    rng = np.random.default_rng(seed)
    x = rng.normal(0, 1, size=n)
    y = np.concatenate([rng.normal(0, 1, size=lag), 0.8 * x[: n - lag]])
    return x, y


def test_flow_finds_direction_and_delay():
    from src.lagflow import lag_flow

    x, y = _pair()
    fwd = lag_flow(x, y, max_lag=12)  # x -> y ?
    bwd = lag_flow(y, x, max_lag=12)
    assert fwd["score"] > bwd["score"]
    assert abs(fwd["delay"] - 6) <= 2


def test_flow_quiet_on_independent():
    from src.lagflow import lag_flow

    rng = np.random.default_rng(1)
    x, y = rng.normal(0, 1, size=300), rng.normal(0, 1, size=300)
    f = lag_flow(x, y, max_lag=12)
    assert f["score"] < 0.4
