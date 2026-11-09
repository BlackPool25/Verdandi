"""Delay-aware pairwise flow: AR(1) pre-whiten + lag-scan max|corr| (walk edges).

Operates on residuals so shared AR texture doesn't fake coupling.
Delay = argmax lag; score = max |corr|. CPU, closed form, no fitting.
"""

from __future__ import annotations

import numpy as np


def _whiten(v: np.ndarray, pre_n: int = 30) -> np.ndarray:
    x = np.asarray(v, dtype=float)
    pre = x[: max(10, pre_n)]
    a = float(np.corrcoef(pre[:-1], pre[1:])[0, 1]) if len(pre) > 2 else 0.0
    a = float(np.clip(a, -0.95, 0.95))
    r = np.empty_like(x)
    r[0] = x[0]
    r[1:] = x[1:] - a * x[:-1]
    return r


def lag_flow(x: np.ndarray, y: np.ndarray, max_lag: int = 12) -> dict:
    """Flow x -> y: max over lags of corr(x[t], y[t+lag]) on whitened series."""
    xw = _whiten(np.asarray(x, dtype=float))
    yw = _whiten(np.asarray(y, dtype=float))
    n = min(len(xw), len(yw))
    xw, yw = xw[:n], yw[:n]
    best, blag = 0.0, 0
    for lag in range(max_lag + 1):
        if lag >= n - 5:
            break
        c = float(np.corrcoef(xw[: n - lag], yw[lag:])[0, 1])
        if abs(c) > abs(best):
            best, blag = c, lag
    return {"score": abs(best), "delay": blag, "signed": best}
