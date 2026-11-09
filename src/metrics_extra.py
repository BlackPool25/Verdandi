"""Deployment-grade metric extras: PA%K window decisions, clustered CIs.

PA%K: a predicted-positive window counts as a kept alarm only if its overlap
with any ground-truth fault span is >= K of the window width. At K -> 0 this
is any-overlap (the permissive labeling the model trained on); at K = 0.5 a
window must be mostly fault. Reporting F1 across K separates sharp detectors
from dilators.
Clustered CIs: episode outcomes are correlated within machines — resample
clusters (default: episode), not windows.
"""

from __future__ import annotations

import numpy as np


def pak_keep(
    decisions: np.ndarray,
    starts: np.ndarray,
    spans: list[tuple[int, int]],
    *,
    w: int,
    k: float,
) -> np.ndarray:
    """Zero-out positive windows whose fault overlap fraction is below K."""
    d = np.asarray(decisions, dtype=int)
    st = np.asarray(starts, dtype=int)
    keep = np.zeros_like(d)
    for i, (a, s) in enumerate(zip(d.tolist(), st.tolist())):
        if not a:
            continue
        ov = 0
        for t0, t1 in spans:
            ov = max(ov, min(s + w, t1) - max(s, t0))
        if ov / w >= k:
            keep[i] = 1
    return keep


def clustered_ci(
    values: np.ndarray,
    clusters: np.ndarray,
    *,
    n_boot: int = 2000,
    seed: int = 0,
    level: float = 0.95,
) -> tuple[float, float]:
    """Percentile bootstrap CI of the mean, resampling whole clusters."""
    import math

    rng = np.random.default_rng(seed)
    v = np.asarray(values, dtype=float)
    c = np.asarray(clusters)
    u = np.unique(c)
    alpha = 1.0 - level
    means = np.empty(n_boot)
    for b in range(n_boot):
        pick = rng.choice(u, size=len(u), replace=True)
        m = np.concatenate([v[c == x] for x in pick])
        means[b] = m.mean() if len(m) else float("nan")
    lo = float(np.nanquantile(means, alpha / 2))
    hi = float(np.nanquantile(means, 1 - alpha / 2))
    if math.isnan(lo) or math.isnan(hi):
        return (0.0, 1.0)
    return (lo, hi)
