"""Tests for src/fusion.py — shrunk Chair-Varshney fusion + suppression."""

import numpy as np
import pytest

from src.fusion import (
    cv_weights,
    estimate_reliabilities,
    fuse,
    fuse_counting,
    shrink,
    suppress,
)


def test_cv_weights_match_oracle_form():
    w1, w0 = cv_weights(0.8, 0.05)
    assert w1 == pytest.approx(np.log(16.0)) and w0 == pytest.approx(np.log(0.2 / 0.95))


def test_small_family_shrinks_to_global():
    assert shrink(0.9, 0.7, 26) == pytest.approx(26 / 46 * 0.9 + 20 / 46 * 0.7)


def test_suppression_keeps_first_alert_with_count():
    kept, reason = suppress(True, ("E1", "M1"), window=5, ledger={})
    kept2, reason2 = suppress(True, ("E1", "M1"), window=5, ledger={("E1", "M1"): 1})
    assert kept and not kept2 and "suppressed-count=1" in reason2


def test_estimate_reliabilities_laplace():
    pd_hat, pfa_hat = estimate_reliabilities(8, 1, 10, 100)
    assert pd_hat == pytest.approx(9 / 12) and pfa_hat == pytest.approx(2 / 102)


def test_fuse_thresholds_weighted_votes():
    assert fuse([True, False], [2.0, 1.0], [-0.5, -1.0], threshold=0.5) is True
    assert fuse([True, False], [2.0, 1.0], [-0.5, -1.0], threshold=1.5) is False


def test_fuse_counting_needs_k_votes():
    assert fuse_counting([True, False, True], k=2) is True
    assert fuse_counting([True, False, True], k=3) is False
