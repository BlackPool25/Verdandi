"""Multi-onset via exact penalized DP (PELT-style, L2 cost, no deps).

Cost of segment [s,e): sum (x - mean)^2. Minimize total cost +
penalty * n_segments via DP; O(n^2) exact (n=285 trivial).
Returns changepoints (end-exclusive boundaries) sorted.
"""

from __future__ import annotations

import numpy as np


def pelt_l2(x: np.ndarray, penalty: float = 10.0, min_size: int = 5) -> list[int]:
    """Exact penalized segmentation for mean shifts (L2 cost)."""
    v = np.asarray(x, dtype=float)
    n = len(v)
    if n < 2 * min_size:
        return []
    c1 = np.zeros(n + 1)
    c2 = np.zeros(n + 1)
    c1[1:] = np.cumsum(v)
    c2[1:] = np.cumsum(v * v)

    def cost(s: int, e: int) -> float:
        m = e - s
        if m < 1:
            return 0.0
        s1 = c1[e] - c1[s]
        s2 = c2[e] - c2[s]
        return float(s2 - s1 * s1 / m)

    INF = float("inf")
    best = np.full(n + 1, INF)
    prev = np.full(n + 1, -1, dtype=int)
    best[0] = -penalty
    # Vectorized inner loop: cost(s,e) for all s via cumsum arrays.
    idx = np.arange(n + 1)
    for e in range(1, n + 1):
        m = e - idx[:e]
        s1 = c1[e] - c1[:e]
        s2 = c2[e] - c2[:e]
        with np.errstate(invalid="ignore", divide="ignore"):
            seg_cost = np.where(m > 0, s2 - s1 * s1 / np.maximum(m, 1), 0.0)
        cand = best[:e] + seg_cost + penalty
        s = int(np.argmin(cand))
        best[e] = float(cand[s])
        prev[e] = s
    cps: list[int] = []
    e = n
    while e > 0 and prev[e] >= 0:
        s = int(prev[e])
        if s > 0:
            cps.append(s)
        e = s
    return sorted(cps)
