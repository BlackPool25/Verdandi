"""Per-family specialists: variable masks + accumulation heads.

VS-MEWMA discipline (Jiang 2012): select the informative variable subset
first (sensitivity gain by dimension reduction), then monitor the subset.
EWMA leads for drift faults; CUSUM (k=0.5σ, h from healthy-run ARL) for
bias/spike onsets. Thresholds tuned on clean runs for target FAR — never
on fault runs.
"""

import numpy as np


def select_mask(X_clean: np.ndarray, k: int = 5, seed: int = 0) -> list[int]:
    """Top-k channels by variance on clean data (stable, seed-independent)."""
    X = np.asarray(X_clean, dtype=float)
    v = X.var(axis=0)
    order = np.argsort(-v, kind="stable")
    return sorted(int(i) for i in order[:k])


def ewma_head(x: np.ndarray, lam: float = 0.3, k: float = 3.0) -> np.ndarray:
    """EWMA exceedance flags: |z_t| > k on the EWMA statistic (zero-mean unit input)."""
    z = np.asarray(x, dtype=float)
    s = 0.0
    out = np.zeros(len(z), dtype=bool)
    for i, v in enumerate(z):
        s = lam * v + (1 - lam) * s
        # steady-state EWMA sd for unit-variance input
        sd = (lam / (2 - lam)) ** 0.5
        out[i] = abs(s) > k * sd
    return out


def cusum_head(x: np.ndarray, k: float = 0.5, h: float = 5.0) -> int | None:
    """Two-sided tabular CUSUM: first alarm index or None (unit-scale input)."""
    z = np.asarray(x, dtype=float)
    gp = gn = 0.0
    for i, v in enumerate(z):
        gp = max(0.0, gp + v - k)
        gn = max(0.0, gn - v - k)
        if gp > h or gn > h:
            return int(i)
    return None
