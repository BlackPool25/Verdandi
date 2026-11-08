"""Chair-Varshney fusion with shrinkage + suppression (M0b-T precision control).

Reliabilities are Laplace-smoothed; per-family estimates shrink to the pooled
global (families <50-100 positives inherit the shrunk/global value at call time).
No-information fallback: fuse_counting (k-out-of-N).
"""

from __future__ import annotations

import math

import numpy as np


def estimate_reliabilities(tp: int, fp: int, p: int, n: int) -> tuple[float, float]:
    """Laplace-smoothed (Pd, Pfa): (TP+1)/(P+2), (FP+1)/(N+2)."""
    return (tp + 1) / (p + 2), (fp + 1) / (n + 2)


def shrink(fam: float, glob: float, n: int, c: int = 20) -> float:
    """Shrink a per-family estimate toward global: lam=n/(n+c)."""
    lam = n / (n + c)
    return lam * fam + (1 - lam) * glob


def cv_weights(pd: float, pfa: float) -> tuple[float, float]:
    """Chair-Varshney log-odds: (log(Pd/Pfa), log((1-Pd)/(1-Pfa)))."""
    return math.log(pd / pfa), math.log((1 - pd) / (1 - pfa))


def fuse(
    votes: list[bool],
    w_pos: list[float],
    w_neg: list[float],
    *,
    threshold: float = 0.0,
) -> bool:
    """Thresholded weighted vote (equal priors at threshold 0)."""
    total = sum(wp if v else wn for v, wp, wn in zip(votes, w_pos, w_neg))
    return bool(total > threshold)


def fuse_counting(votes: list[bool], *, k: int) -> bool:
    """k-out-of-N fallback when reliabilities are untrusted."""
    return sum(1 for v in votes if v) >= k


def episode_decision(
    expert_flags: dict[str, np.ndarray], *, k: int = 3, window: int = 5
) -> np.ndarray:
    """Episode-level decision: OR screen (recall) + k-of-N dwell confirm (precision).

    A single-tick firing is suppressed; only sustained agreement (any expert, or
    the same one) inside a trailing window survives. Window must be shorter than
    the shortest fault duration (8 ticks) so real episodes are never gated out.
    """
    names = sorted(expert_flags)
    if not names:
        return np.array([], dtype=bool)
    n = len(np.asarray(expert_flags[names[0]]))
    screen = np.zeros(n, dtype=bool)
    for name in names:
        screen |= np.asarray(expert_flags[name], dtype=bool)
    if k <= 1:
        return screen
    counts = np.convolve(screen.astype(int), np.ones(window, dtype=int), mode="full")[:n]
    starts = np.zeros(n, dtype=int)
    starts[1:] = counts[:-1]
    return screen & (starts + screen.astype(int) >= k)


def suppress(alarm: bool, key: tuple, window: int, ledger: dict) -> tuple[bool, str]:
    """Suppression keyed (expert, entity): first alert kept, repeats within the
    window suppressed with count + reason; window expiry forces re-alert."""
    if not alarm:
        return False, "no-alarm"
    n = int(ledger.get(key, 0))
    if n == 0:
        ledger[key] = 1
        return True, "first-alert"
    if n > window:
        ledger[key] = 1
        return True, "window-expired-realarm"
    ledger[key] = n + 1
    return False, f"suppressed-count={n}"
