"""Dense onset: ±tick band targets + causal smoothing + refractory peak-pick.

Inference uses past taps only. compare mBOCD lesson: explicit
change-vs-growth comparison beats argmax smoothing.
"""

from __future__ import annotations

import numpy as np


def make_targets(
    t0_steps: np.ndarray, n: int, half: int = 2
) -> tuple[np.ndarray, np.ndarray]:
    """y_onset band [t0-half, t0+half], y_fault t>=t0. t0<0 rows are clean."""
    t0_steps = np.asarray(t0_steps)
    yo = np.zeros(n, dtype=int)
    yf = np.zeros(n, dtype=int)
    for t0 in t0_steps:
        t0 = int(t0)
        if t0 < 0:
            continue
        lo, hi = max(0, t0 - half), min(n, t0 + half + 1)
        yo[lo:hi] = 1
        yf[t0:] = 1
    return yo, yf


def smooth_causal(p: np.ndarray, k: int = 5) -> np.ndarray:
    """Causal median filter (past taps only) + short causal mean."""
    p = np.asarray(p, dtype=float)
    out = np.zeros_like(p)
    for t in range(len(p)):
        lo = max(0, t - k + 1)
        out[t] = float(np.median(p[lo : t + 1]))
    return out


def pick_onset(
    p: np.ndarray,
    delta: float = 0.15,
    tau: float = 0.5,
    w: int = 45,
) -> int:
    """First tick where novelty and level both fire; -1 if never."""
    p = np.asarray(p, dtype=float)
    floor = np.zeros_like(p)
    run_min = float("inf")
    for t in range(len(p)):
        lo = max(0, t - w)
        seg = p[lo : t + 1] if t > lo else p[t : t + 1]
        run_min = float(np.min(seg)) if len(seg) else p[t]
        floor[t] = run_min
    nov = p - floor
    for t in range(len(p)):
        if nov[t] > delta and p[t] > tau:
            return t
    return -1
