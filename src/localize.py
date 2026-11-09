"""Trigger-gated tick-level onset localization (no score blending).

The w128 detector fires (trigger); the onset comes 100% from a tick-level
statistic inside a bounded ROI around the trigger — never from blending
window scores (killed twice: mean-fusion 0.67, gated-combiner 0.63).
- Structural families (delay/loss/breakdown): counter-run edge — counters are
  step functions at onset; the first tick of the overlapping positive run.
- Abrupt obs families (spike/bias/quality): Page-CUSUM backtrack on the
  residual projection; onset = last zero-crossing of g before the trigger.
- Gradual (drift): EWMA(0.15) control-limit crossing on the same projection.
"""

from __future__ import annotations

import numpy as np


def counter_edge(
    counter: np.ndarray, trigger: int, *, half_roi: int = 64
) -> int | None:
    """First tick of the positive run overlapping the trigger window."""
    c = np.asarray(counter, dtype=float)
    lo, hi = max(0, trigger - half_roi), min(len(c), trigger + 8)
    pos = np.flatnonzero(c[lo:hi] > 0)
    if len(pos) == 0:
        return None
    start = pos[0]
    while start > 0 and c[lo + start - 1] > 0:
        start -= 1
    return int(lo + start)


def cusum_backtrack(
    resid: np.ndarray,
    trigger: int,
    *,
    k: float = 1.0,
    h: float = 5.0,
    half_roi: int = 64,
) -> int | None:
    """Page-CUSUM forward to trigger, then onset = last zero-crossing of g.

    k should be ~half the shift to detect, in noise-σ units (k=1 detects
    ~2σ shifts; larger shifts want larger k so g still resets in noise).
    """
    r = np.asarray(resid, dtype=float)
    lo, hi = max(0, trigger - half_roi), min(len(r), trigger + 8)
    seg = r[lo:hi]
    if len(seg) < 2:
        return None
    mu = float(np.median(seg[: max(1, len(seg) // 4)]))
    sd = float(np.median(np.abs(seg[: max(1, len(seg) // 4)] - mu)) * 1.4826) or 1.0
    z = (seg - mu) / sd
    g, last_zero, alarm = 0.0, 0, None
    for i, v in enumerate(z):
        g = max(0.0, g + abs(v) - k)
        if g == 0.0:
            last_zero = i
        if g > h:
            alarm = i
            break
    if alarm is None:
        return None
    return int(lo + min(last_zero + 1, alarm))


def ewma_onset(
    resid: np.ndarray,
    trigger: int,
    *,
    lam: float = 0.15,
    limit_sd: float = 3.0,
    half_roi: int = 64,
) -> int | None:
    """EWMA control-limit crossing for gradual changes (drift)."""
    r = np.asarray(resid, dtype=float)
    lo, hi = max(0, trigger - half_roi), min(len(r), trigger + 8)
    seg = r[lo:hi]
    if len(seg) < 2:
        return None
    mu = float(np.median(seg[: max(1, len(seg) // 4)]))
    sd = float(np.std(seg[: max(1, len(seg) // 4)])) or 1.0
    e = mu
    for i, v in enumerate(seg):
        e = lam * v + (1 - lam) * e
        lim = limit_sd * sd * (lam / (2 - lam)) ** 0.5
        if abs(e - mu) > lim:
            return int(lo + i)
    return None
