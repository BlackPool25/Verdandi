"""Risk-coverage tests: abstention tradeoff from OOF scores, no hand gates."""

import numpy as np
import pandas as pd


def _oof(n=400, seed=0):
    rng = np.random.default_rng(seed)
    y = (rng.random(n) < 0.15).astype(int)
    score = np.clip(rng.normal(0.1, 0.1, n) + y * rng.normal(0.8, 0.15, n), 0, 1)
    return pd.DataFrame({"score": score, "y": y})


def test_curve_covers_all_at_zero_threshold():
    from scripts.risk_coverage import risk_coverage

    rc = risk_coverage(_oof())
    assert rc[0][0] == 1.0  # coverage 1.0 at tau=0
    assert all(0.0 <= r <= 1.0 for _, r in rc)


def test_risk_falls_as_threshold_rises():
    from scripts.risk_coverage import risk_coverage

    rc = risk_coverage(_oof())
    cov = [c for c, _ in rc]
    risk = [r for _, r in rc]
    assert cov == sorted(cov, reverse=True)
    assert risk[0] >= risk[-1]


def test_empty_frame_returns_empty():
    from scripts.risk_coverage import risk_coverage

    assert risk_coverage(pd.DataFrame({"score": [], "y": []})) == []


def test_pick_point_takes_highest_coverage_within_budget():
    from scripts.risk_coverage import pick_point

    rc = [(1.0, 0.10), (0.9, 0.04), (0.5, 0.01)]
    cov, _tau = pick_point(rc, max_risk=0.05)
    assert cov == 0.9
