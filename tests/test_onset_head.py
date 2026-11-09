"""Dense per-timestep onset head: targets + causal peak-pick (TDD RED)."""

import numpy as np


def test_onset_band_targets():
    from src.onset_head import make_targets

    t0 = np.array([100, -1, 100])
    yo, yf = make_targets(t0, n=110, half=2)
    assert yo[98:103].sum() == 5 and yo.sum() == 5
    assert yf[100:].sum() == 10 and yf[:100].sum() == 0


def test_peak_pick_first_rising_edge():
    from src.onset_head import pick_onset

    p = np.zeros(200)
    p[50:80] = 0.9
    p[150:170] = 0.95
    assert pick_onset(p, delta=0.15, tau=0.5) == 50


def test_peak_pick_causal_no_future_leak():
    from src.onset_head import smooth_causal

    p = np.zeros(100)
    p[80:] = 1.0
    s = smooth_causal(p, k=5)
    assert (s[:80] < 0.5).all()  # future spike never leaks backwards
    assert s[85] > 0.5
