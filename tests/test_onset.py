"""Multi-onset tests (PELT exact DP, no new deps)."""

import numpy as np


def _series(n=285, cps=(), mags=()):
    rng = np.random.default_rng(0)
    x = rng.normal(0, 1, size=n)
    for cp, m in zip(cps, mags):
        x[cp:] += m
    return x


def test_pelt_finds_two_offsets():
    from src.onset import pelt_l2

    x = _series(cps=(100, 200), mags=(5.0, -4.0))
    cps = pelt_l2(x, penalty=10.0, min_size=10)
    assert any(abs(c - 100) <= 4 for c in cps), cps
    assert any(abs(c - 200) <= 4 for c in cps), cps


def test_pelt_clean_finds_nothing():
    from src.onset import pelt_l2

    x = _series()
    assert pelt_l2(x, penalty=10.0, min_size=10) == []


def test_pelt_short_fault_not_oversmoothed():
    from src.onset import pelt_l2

    x = _series(cps=(150, 162), mags=(6.0, -6.0))
    cps = pelt_l2(x, penalty=10.0, min_size=5)
    assert any(abs(c - 150) <= 4 for c in cps), cps
