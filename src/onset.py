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


def crops_elbow(x: np.ndarray, penalties: tuple[float, ...]) -> list[int]:
    """CROPS-lite: PELT over a penalty grid, elbow-picked segmentation.

    Runs pelt_l2 at each penalty (ascending → fewer changepoints).
    Picks the segmentation at max curvature of the (n_cps vs log-penalty)
    curve — the point where raising the penalty stops removing real
    structure and starts keeping noise. Returns its changepoints.
    """
    v = np.asarray(x, dtype=float)
    pens = sorted({float(p) for p in penalties if p > 0})
    if len(v) < 10 or not pens:
        return []
    segs = [(p, pelt_l2(v, penalty=p)) for p in pens]
    counts = np.array([len(c) for _, c in segs], dtype=float)
    if counts.max() == 0:
        return []
    # elbow: largest drop in count per log-penalty step (structure->noise knee)
    lp = np.log(np.array([p for p, _ in segs]))
    drops = -np.diff(counts) / np.maximum(np.diff(lp), 1e-9)
    if len(drops) == 0 or bool((drops <= 0).all()):
        return list(segs[-1][1])
    knee = int(np.argmax(drops)) + 1
    return list(segs[knee][1])


def page_cusum(
    x: np.ndarray, k: float = 0.5, h: float = 5.0, min_gap: int = 10
) -> list[int]:
    """Two-sided Page CUSUM on standardized residuals; reset after firing.

    g+ accumulates (x - k), g- accumulates (-x - k); a hit fires at the
    first index with g > h, then both reset (refractory min_gap).
    h ~= 4-5 targets ARL0 of a few hundred on ~N(0,1) input.
    """
    v = np.asarray(x, dtype=float)
    if len(v) == 0 or not (0.0 <= k) or h <= 0.0:
        raise ValueError(f"k in [0,1] and h > 0 required, got k={k!r} h={h!r}")
    hits: list[int] = []
    gp = gn = 0.0
    last = -min_gap - 1
    for i, xi in enumerate(v):
        gp = max(0.0, gp + (float(xi) - k))
        gn = max(0.0, gn + (-float(xi) - k))
        if (gp > h or gn > h) and i - last > min_gap:
            hits.append(i)
            last = i
            gp = gn = 0.0
    return hits
