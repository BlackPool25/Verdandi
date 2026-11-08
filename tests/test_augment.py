"""Synthetic injection tests (COE chunk-swap + IQR point outliers)."""

from __future__ import annotations

import numpy as np


def test_coe_swap_breaks_temporal_relation_and_labels_minority():
    from src.augment import coe_swap

    rng = np.random.default_rng(0)
    x = rng.normal(0, 1, size=(64, 3))
    xa, ya = coe_swap(x, np.zeros(64, dtype=int), rng=rng, frac=0.25)
    assert xa.shape == x.shape and ya.sum() > 0
    assert not np.array_equal(xa[ya == 1], x[ya == 1])


def test_point_outlier_scales_to_iqr_and_labels_spike():
    from src.augment import point_outliers

    rng = np.random.default_rng(1)
    x = rng.normal(10, 1, size=(200, 2))
    xa, ya = point_outliers(x, np.zeros(200, dtype=int), rng=rng, n=5)
    assert ya.sum() == 5
    assert float(np.abs(xa[ya == 1] - 10).mean()) > 3.0
