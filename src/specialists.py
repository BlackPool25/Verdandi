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


def ewma_head(x: np.ndarray, lam: float = 0.3, k: float = 3.0, burnin: int = 50) -> np.ndarray:
    """EWMA exceedance flags: |z_t| > k on the EWMA statistic (zero-mean unit input).

    burnin startup samples are never flagged (transient variance).
    """
    z = np.asarray(x, dtype=float)
    s = 0.0
    out = np.zeros(len(z), dtype=bool)
    for i, v in enumerate(z):
        s = lam * v + (1 - lam) * s
        # steady-state EWMA sd for unit-variance input
        sd = (lam / (2 - lam)) ** 0.5
        out[i] = (i >= burnin) and abs(s) > k * sd
    return out


def lagged_stats(seq: np.ndarray, d: int = 10) -> np.ndarray:
    """D-PCA-style dynamic augmentation: trailing lag-mean + lag-max per channel.

    seq: (T, C) window-stat sequence -> (T, 2C). Deterministic, causal
    (window [t-d+1, t] only).
    """
    S = np.asarray(seq, dtype=float)
    T, C = S.shape
    out = np.zeros((T, 2 * C))
    for t in range(T):
        w = S[max(0, t - d + 1):t + 1]
        out[t, :C] = w.mean(axis=0)
        out[t, C:] = w.max(axis=0)
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


def fit_family_mask(X_clean: np.ndarray, X_fault: np.ndarray, k: int = 5) -> list[int]:
    """Top-k channels by standardized mean shift (fault vs clean)."""
    mu0, sd0 = X_clean.mean(axis=0), X_clean.std(axis=0) + 1e-9
    shift = np.abs((X_fault.mean(axis=0) - mu0) / sd0)
    order = np.argsort(-shift, kind="stable")
    return sorted(int(i) for i in order[:k])


def expert_score(X: np.ndarray, mask: list[int], mu0: np.ndarray, sd0: np.ndarray) -> np.ndarray:
    """Per-window masked mean |z| — the variant-1 episode/window score."""
    Z = (np.asarray(X, dtype=float) - mu0) / (np.asarray(sd0) + 1e-9)
    return np.abs(Z[:, list(mask)]).mean(axis=1)


def trajectory_score(T: np.ndarray, h: float = 5.0, k: float = 0.5) -> int:
    """Variant-2: CUSUM alarm (1) / no alarm (0) on a per-episode trajectory."""
    return 1 if cusum_head(np.asarray(T, dtype=float), k=k, h=h) is not None else 0


def tune_h(clean_trajs: list[np.ndarray], far: float = 0.05, k: float = 0.5) -> float:
    """Largest h with clean-episode alarm rate <= far (grid search)."""
    for h in (3.0, 4.0, 5.0, 6.0, 8.0, 10.0, 12.0, 15.0):
        r = np.mean([trajectory_score(t, h=h, k=k) for t in clean_trajs])
        if r <= far:
            return h
    return 15.0
