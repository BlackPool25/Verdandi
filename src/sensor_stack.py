"""Sensor stack: D-PCA augmentation -> RBC-T2 (+PDC-Q challenger) -> EBF.

Method per Cartocci et al 2212.06688: D-PCA (d delays) first — temporal
correlation is the biggest lever; RBC-T2 contributions for isolation;
EBF (+0.01 winner / -0.005 rest, clip [0,1], thr 0.2) kills transient FAs.
"""

import numpy as np


def dpca_augment(X: np.ndarray, d: int = 10) -> np.ndarray:
    """Stack [x(k) ... x(k-d)] rows; (T, n) -> (T-d+1, n*d), causal only."""
    X = np.asarray(X, dtype=float)
    T, n = X.shape
    return np.hstack([X[d - k:T - k if T - k > 0 else None] for k in range(d + 1)])


def fit_pca(Zc: np.ndarray, var_keep: float = 0.98):
    """PCA on clean D-PCA matrix: (P, lam, mu, sd), l = min comps for var_keep."""
    Z = np.asarray(Zc, dtype=float)
    mu, sd = Z.mean(axis=0), Z.std(axis=0) + 1e-12
    C = np.cov(((Z - mu) / sd).T)
    lam, P = np.linalg.eigh(C)
    order = np.argsort(-lam)
    lam, P = lam[order], P[:, order]
    cum = np.cumsum(lam) / lam.sum()
    l = int(np.searchsorted(cum, var_keep)) + 1
    return P[:, :l], lam[:l], mu, sd


def _residual(Z: np.ndarray, P: np.ndarray, mu: np.ndarray, sd: np.ndarray) -> np.ndarray:
    Zn = (np.asarray(Z, dtype=float) - mu) / (sd + 1e-12)
    return Zn - (Zn @ P) @ P.T


def rbc_t2(Z: np.ndarray, P: np.ndarray, lam: np.ndarray, mu: np.ndarray, sd: np.ndarray) -> np.ndarray:
    """RBC-T2 (eq 20): (xi' D x)^2 / d_ii with D = P diag(1/lam) P'."""
    Zn = (np.asarray(Z, dtype=float) - mu) / (sd + 1e-12)
    D = (P / np.maximum(lam, 1e-12)) @ P.T
    Dx = Zn @ D.T
    d = np.diag(D) + 1e-12
    return (Dx ** 2) / d


def pdc_q(Z: np.ndarray, P: np.ndarray, mu: np.ndarray, sd: np.ndarray) -> np.ndarray:
    """Plain Q-contributions (eq 13): (xi' C x)^2 — the challenger."""
    r = _residual(Z, P, mu, sd)
    return r ** 2


def ebf_filter(argmax_idx: np.ndarray, n_vars: int, up: float = 0.01,
               down: float = 0.005, thr: float = 0.2) -> np.ndarray:
    """Evidence accumulation per variable: reward winner, penalize rest."""
    idx = np.asarray(argmax_idx, dtype=int)
    s = np.zeros(n_vars)
    out = np.zeros(len(idx), dtype=bool)
    for k, j in enumerate(idx):
        s += -down
        s[j] += up + down
        s = np.clip(s, 0.0, 1.0)
        out[k] = s[j] >= thr
    return out
