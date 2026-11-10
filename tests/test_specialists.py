"""Task 3: per-family specialists (TDD RED)."""

import numpy as np


def test_mask_stable_across_seeds():
    from src.specialists import select_mask

    rng = np.random.default_rng(0)
    Xc = rng.normal(0, 1, (500, 10))
    Xc[:, 3] *= 0.2  # low-variance channel
    m1 = select_mask(Xc, k=4, seed=0)
    m2 = select_mask(Xc, k=4, seed=1)
    assert len(m1) == 4 and set(m1) == set(m2)


def test_ewma_quiet_on_clean():
    from src.specialists import ewma_head

    rng = np.random.default_rng(0)
    x = rng.normal(0, 1, 300)
    hits = ewma_head(x, lam=0.3, k=3.0)
    assert hits.sum() / len(x) <= 0.01  # bounded FAR on clean (ARL-tuned h)


def test_cusum_detects_ramp_fast():
    from src.specialists import cusum_head

    rng = np.random.default_rng(0)
    x = np.concatenate([rng.normal(0, 1, 100), np.linspace(0, 3, 60)])
    det = cusum_head(x, k=0.5, h=5.0)
    assert det is not None and det < 160  # caught within the ramp
