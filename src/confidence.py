"""Post-hoc calibration: temperature scaling + Platt + coverage gate.

Guo et al 2017: single-parameter temperature is the best practical
multiclass calibrator. Platt (2-param sigmoid) is the safe small-sample
choice for correctness probabilities. Coverage follows the selective
classification risk-coverage curve (El-Yaniv & Wiener): threshold the
confidence on held-out data, report risk at each coverage.
"""

import numpy as np


def _softmax(logits: np.ndarray, T: float) -> np.ndarray:
    z = np.asarray(logits, dtype=float) / max(T, 1e-12)
    z -= z.max(axis=1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=1, keepdims=True)


def nll(logits: np.ndarray, T: float, y: np.ndarray) -> float:
    p = _softmax(logits, T)
    return float(-np.log(p[np.arange(len(y)), np.asarray(y).astype(int)] + 1e-15).mean())


def fit_temperature(logits: np.ndarray, y: np.ndarray,
                    lo: float = 0.05, hi: float = 20.0, iters: int = 60) -> float:
    """Golden-section minimization of NLL over T (no scipy needed)."""
    gr = (5 ** 0.5 - 1) / 2
    a, b = lo, hi
    c, d = b - gr * (b - a), a + gr * (b - a)
    fc, fd = nll(logits, c, y), nll(logits, d, y)
    for _ in range(iters):
        if fc < fd:
            b, fd = d, fc
            d, c = c, b - gr * (b - a)
            fc = nll(logits, c, y)
        else:
            a, fc = c, fd
            c, d = d, a + gr * (b - a)
            fd = nll(logits, d, y)
    return float((a + b) / 2)


def ece_score(probs: np.ndarray, y: np.ndarray, n_bins: int = 15) -> float:
    """Top-label ECE with equal-width bins (Guo et al 2017)."""
    p = np.asarray(probs, dtype=float)
    y = np.asarray(y).astype(int)
    conf = p.max(axis=1)
    pred = p.argmax(axis=1)
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    tot = 0.0
    for b in range(n_bins):
        m = (conf > edges[b]) & (conf <= edges[b + 1] if b else conf <= edges[1])
        if b == 0:
            m = (conf >= edges[0]) & (conf <= edges[1])
        if m.sum() == 0:
            continue
        tot += m.mean() * abs((pred[m] == y[m]).mean() - conf[m].mean())
    return float(tot)


def platt_fit(margins: np.ndarray, correct: np.ndarray, iters: int = 100) -> tuple[float, float]:
    """2-param sigmoid P(correct) = 1/(1+exp(a*m+b)) via Newton IRLS."""
    m = np.asarray(margins, dtype=float)
    t = np.asarray(correct, dtype=float)
    w = np.zeros(2)  # [a, b]
    X = np.column_stack([m, np.ones_like(m)])
    for _ in range(iters):
        p = 1.0 / (1.0 + np.exp(-(X @ w)))
        g = X.T @ (p - t) / len(t)
        W = p * (1 - p) + 1e-9
        H = (X.T * W) @ X / len(t) + np.eye(2) * 1e-6
        step = np.linalg.solve(H, g)
        w -= step
        if np.abs(step).max() < 1e-10:
            break
    return float(w[0]), float(w[1])


def platt_predict(margins: np.ndarray, a: float, b: float) -> np.ndarray:
    m = np.asarray(margins, dtype=float)
    return 1.0 / (1.0 + np.exp(-(a * m + b)))


def coverage_curve(conf: np.ndarray, correct: np.ndarray) -> list[tuple[float, float]]:
    """Risk-coverage points over unique confidence thresholds (descending)."""
    c = np.asarray(conf, dtype=float)
    t = np.asarray(correct, dtype=int)
    order = np.argsort(-c, kind="stable")
    cs, ts = c[order], t[order]
    pts = [(1.0, float(1 - ts.mean()))]
    for k in range(1, len(cs)):
        pts.append((float(k / len(cs)), float(1 - ts[:k].mean())))
    return pts


def pick_threshold(conf: np.ndarray, correct: np.ndarray, risk_target: float) -> float:
    """Highest-coverage threshold with empirical risk <= target (held-out).

    Returns the smallest confidence tau such that risk(conf >= tau) <=
    risk_target; falls back to max conf (empty cover) if none qualifies.
    """
    c = np.asarray(conf, dtype=float)
    t = np.asarray(correct, dtype=int)
    best = float(c.max())
    for tau in sorted(np.unique(c)):
        m = c >= tau
        if m.sum() > 0 and (1 - t[m].mean()) <= risk_target:
            return float(tau)
    return best
