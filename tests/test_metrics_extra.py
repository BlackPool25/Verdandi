"""PA%K + clustered-CI tests (synthetic)."""

from __future__ import annotations

import numpy as np


def test_pak_keep_filters_low_overlap_windows():
    from src.metrics_extra import pak_keep

    dec = np.array([1, 1, 1])
    starts = np.array([0, 8, 100])
    spans = [(10, 20)]
    kept = pak_keep(dec, starts, spans, w=16, k=0.5)
    # Window [0,16): overlap 6/16 < 0.5 -> dropped. [8,24): 10/16 kept.
    assert kept.tolist() == [0, 1, 0]
    kept_any = pak_keep(dec, starts, spans, w=16, k=0.0)
    assert kept_any.tolist() == [1, 1, 0]


def test_clustered_ci_covers_mean_and_shrinks_with_clusters():
    from src.metrics_extra import clustered_ci

    rng = np.random.default_rng(0)
    vals = rng.integers(0, 2, size=200).astype(float)
    cl = np.repeat(np.arange(20), 10)
    lo, hi = clustered_ci(vals, cl, n_boot=500, seed=1)
    assert lo <= vals.mean() <= hi and (hi - lo) < 0.5
