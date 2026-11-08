"""Tests for src/calibrate_3arm.py — 3-arm calibration on clean-validation scores."""

import numpy as np
import pytest

from src.calibrate_3arm import fit_gmm_threshold, fit_quantile_threshold


def test_quantile_arm_marks_top_one_percent():
    scores = np.arange(1000, dtype=float)
    tau = fit_quantile_threshold(scores, fpr_target=0.01)
    assert (scores > tau).mean() == pytest.approx(0.01, abs=0.002)


def test_gmm_arm_selects_two_modes_and_thresholds_tail():
    rng = np.random.default_rng(0)
    scores = np.concatenate([rng.normal(0, 1, 800), rng.normal(5, 1, 200)])
    tau, k = fit_gmm_threshold(scores, fpr_target=0.01)
    assert k == 2
    assert (scores > tau).mean() == pytest.approx(0.01, abs=0.01)
