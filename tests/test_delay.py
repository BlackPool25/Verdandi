"""Delay-track tests: inter-departure CUSUM vs prefix baseline."""

import numpy as np


def _gaps(prefix=5.0, fault=8.0, n0=40, n1=20, seed=0):
    rng = np.random.default_rng(seed)
    pre = rng.exponential(prefix, size=n0)
    post = rng.exponential(fault, size=n1)
    return pre, post


def test_cusum_fires_on_elongation():
    from src.delay import cusum_on_gaps

    pre, post = _gaps()
    idx = cusum_on_gaps(pre, post, k=1.0, h=5.0)
    assert idx is not None and idx < 20


def test_cusum_quiet_on_no_shift():
    from src.delay import cusum_on_gaps

    rng = np.random.default_rng(1)
    pre = rng.exponential(5.0, size=40)
    post = rng.exponential(5.0, size=20)
    assert cusum_on_gaps(pre, post, k=1.0, h=8.0) is None
