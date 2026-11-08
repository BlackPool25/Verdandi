"""Tests for src/vus_pr.py — simplified range-based VUS-PR (threshold-free primary)."""

import numpy as np
import pytest

from src.vus_pr import range_pr_auc, vus_pr


def test_perfect_scores_auc_one():
    scores = np.array([0.1, 0.2, 0.9, 0.95, 0.1, 0.2])
    labels = np.array([0, 0, 1, 1, 0, 0])
    assert range_pr_auc(scores, labels, buffer=0) == pytest.approx(1.0, abs=0.02)


def test_inverted_scores_auc_low():
    rng = np.random.default_rng(0)
    scores = rng.normal(0, 1, size=210)
    scores[200:] += 5.0  # high scores sit on negatives...
    labels = np.zeros(210, dtype=int)
    labels[:10] = 1  # ...while positives score low
    assert range_pr_auc(scores, labels, buffer=0) <= 0.15


def test_buffer_forgives_near_miss():
    scores = np.zeros(20)
    scores[5] = 1.0  # alarm adjacent to, not on, the label [7, 9]
    labels = np.zeros(20, dtype=int)
    labels[7:10] = 1
    low = range_pr_auc(scores, labels, buffer=0)
    high = range_pr_auc(scores, labels, buffer=3)
    assert 0.0 <= low < high and high > 0.4


def test_no_positives_is_nan():
    assert np.isnan(range_pr_auc(np.zeros(10), np.zeros(10, dtype=int), buffer=0))
    assert np.isnan(vus_pr(np.zeros(10), np.zeros(10, dtype=int)))


def test_vus_averages_buffers():
    rng = np.random.default_rng(0)
    scores = rng.normal(0, 1, size=200)
    scores[90:110] += 4.0
    labels = np.zeros(200, dtype=int)
    labels[90:110] = 1
    v = vus_pr(scores, labels, buffers=(0, 5, 10))
    assert 0.7 <= v <= 1.0


def test_build_appendix_groups_families_and_wilson(tmp_path):
    import sys

    sys.path.insert(0, str(tmp_path / "scripts-stub"))
    from scripts.m0b_vus_appendix import build_appendix, wilson

    rng = np.random.default_rng(0)
    for name, shift in (("A", 5.0), ("B", 5.0), ("C", 0.0)):
        s = rng.normal(0, 1, size=100)
        lab = np.zeros(100, dtype=int)
        lab[40:60] = 1
        s[40:60] += shift
        np.savez_compressed(tmp_path / f"{name}.npz", scores=s, labels=lab, fault_id=name)
    out = build_appendix(str(tmp_path), {"A": "sig", "B": "sig", "C": "sig"})
    assert out["sig"]["n"] == 3 and 0.0 < out["sig"]["vus_pr_mean"] <= 1.0
    lo, hi = wilson(20, 26)
    assert lo < 0.77 < hi and hi - lo > 0.2
