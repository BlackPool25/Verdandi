"""Delay-track: inter-departure CUSUM vs prefix baseline (O-1 + O-5).

Elongation, not level: delay faults stretch service time by d. Compare
fault-window inter-departure gaps against the prefix baseline with a
one-sided CUSUM; per-machine baselines dodge join dilution. Shrinkage
note: callers must not accept verdicts on <10 fault samples.
"""

from __future__ import annotations

import numpy as np


def cusum_on_gaps(
    gaps_prefix: np.ndarray, gaps_test: np.ndarray, k: float = 1.0, h: float = 5.0
) -> int | None:
    """One-sided CUSUM for mean increase. Returns first alarm index or None."""
    pre = np.asarray(gaps_prefix, dtype=float)
    tst = np.asarray(gaps_test, dtype=float)
    if len(pre) < 5 or len(tst) == 0:
        return None
    mu = float(pre.mean())
    g = 0.0
    for i, x in enumerate(tst):
        g = max(0.0, g + (x - mu - k))
        if g > h:
            return i
    return None


def inter_departure_ticks(flag: np.ndarray, start: int = 0) -> np.ndarray:
    """Gaps between completion ticks (flag==1) at/after start."""
    idx = np.flatnonzero(np.asarray(flag) > 0)
    idx = idx[idx >= start]
    return np.diff(idx).astype(float) if len(idx) >= 2 else np.array([])
