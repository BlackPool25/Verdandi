"""Onset FAR head-to-head tests: CROPS-elbow vs Page-CUSUM vs single-penalty PELT."""

import numpy as np


def _step(n=300, at=200, mag=6.0, seed=0):
    rng = np.random.default_rng(seed)
    x = rng.normal(0, 1, size=n)
    x[at:] += mag
    return x


def test_crops_elbow_finds_step_without_clutter():
    from src.onset import crops_elbow

    x = _step()
    cps = crops_elbow(x, penalties=(5.0, 10.0, 20.0, 40.0, 80.0))
    assert any(abs(c - 200) <= 5 for c in cps), cps
    assert len(cps) <= 3


def test_crops_elbow_quiet_on_clean():
    from src.onset import crops_elbow

    rng = np.random.default_rng(1)
    cps = crops_elbow(rng.normal(0, 1, size=300), penalties=(5.0, 10.0, 20.0, 40.0, 80.0))
    assert len(cps) <= 2


def test_page_cusum_finds_step():
    from src.onset import page_cusum

    x = _step(at=200)
    hits = page_cusum(x, k=0.5, h=5.0)
    assert any(abs(h - 200) <= 10 for h in hits), hits


def test_page_cusum_quiet_on_clean_at_arl():
    from src.onset import page_cusum

    rng = np.random.default_rng(2)
    hits = page_cusum(rng.normal(0, 1, size=1000), k=0.5, h=5.0)
    assert len(hits) <= 3
