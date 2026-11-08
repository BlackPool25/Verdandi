"""In-fold synthetic anomaly injection (COE chunk-swaps + IQR point outliers).

Causal and fold-local: caller augments the train split only; no test rows,
no cross-episode leakage. Labels for injected rows are 1 (minority).
"""

from __future__ import annotations

import numpy as np


def coe_swap(
    x: np.ndarray,
    y: np.ndarray,
    *,
    rng: np.random.Generator | None = None,
    frac: float = 0.10,
    max_len: int = 16,
) -> tuple[np.ndarray, np.ndarray]:
    """Swap a random chunk of a random subset of dims (breaks temporal relation)."""
    r = rng or np.random.default_rng()
    xa, ya = np.array(x, dtype=float), np.array(y, dtype=int).copy()
    n, d = xa.shape
    n_inject = max(1, int(n * frac))
    idx = r.choice(n, size=n_inject, replace=False)
    for i in idx:
        ln = int(min(int(r.integers(2, max_len + 1)), n - int(i)))
        if ln < 2:
            continue
        dims = r.choice(d, size=max(1, d // 2), replace=False)
        donor = int(r.integers(0, n - ln))
        xa[i : i + ln][:, dims] = xa[donor : donor + ln][:, dims]
        ya[i : i + ln] = 1
    return xa, ya


def point_outliers(
    x: np.ndarray,
    y: np.ndarray,
    *,
    rng: np.random.Generator | None = None,
    n: int = 8,
    k_iqr: float = 6.0,
) -> tuple[np.ndarray, np.ndarray]:
    """Add/subtract spikes scaled to trailing IQR at random points/dims."""
    r = rng or np.random.default_rng()
    xa, ya = np.array(x, dtype=float), np.array(y, dtype=int).copy()
    n_rows, d = xa.shape
    q75 = np.quantile(xa, 0.75, axis=0)
    q25 = np.quantile(xa, 0.25, axis=0)
    iqr = np.maximum(q75 - q25, 1e-6)
    idx = r.choice(n_rows, size=min(n, n_rows), replace=False)
    for i in idx:
        dims = r.choice(d, size=max(1, d // 3), replace=False)
        sign = 1.0 if bool(r.integers(0, 2)) else -1.0
        xa[i, dims] += sign * k_iqr * iqr[dims]
        ya[i] = 1
    return xa, ya
