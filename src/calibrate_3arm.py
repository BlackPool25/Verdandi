"""3-arm calibration on clean-validation scores only (Phase C).

Arm A: empirical quantile. Arm B: GMM (+Gamma). Arm C: MOM-SPOT with guardrail.
2-of-3 stability vote + recall-first veto. Never fit on train. Never score test.
"""

import numpy as np
from scipy import stats
from sklearn.mixture import GaussianMixture


def fit_quantile_threshold(scores_clean: np.ndarray, *, fpr_target: float = 0.01) -> float:
    """Empirical-quantile threshold: flag the top `fpr_target` fraction of clean scores."""
    return float(np.quantile(np.asarray(scores_clean, dtype=float), 1.0 - fpr_target))


def fit_gmm_threshold(
    scores_clean: np.ndarray, *, max_components: int = 3, fpr_target: float = 0.01
) -> tuple[float, int]:
    """GMM threshold with Gamma calibration.

    BIC selects K over 1..max_components; the top-mean component is the
    anomaly mode; Gamma fitted to its samples sets the tail so the overall
    flagged fraction is `fpr_target`.
    """
    x = np.asarray(scores_clean, dtype=float).reshape(-1, 1)
    n = x.shape[0]
    best_k, best_bic = 1, GaussianMixture(n_components=1, random_state=0).fit(x).bic(x)
    for k in range(2, max_components + 1):
        bic = GaussianMixture(n_components=k, random_state=0).fit(x).bic(x)
        if bic < best_bic:
            best_k, best_bic = k, bic
    gm = GaussianMixture(n_components=best_k, random_state=0).fit(x)
    top = int(np.argmax(gm.means_.ravel()))
    top_samples = x[gm.predict(x) == top].ravel()
    level = 1.0 - fpr_target * n / max(top_samples.size, 1)
    if top_samples.size <= fpr_target * n or not 0.0 < level < 1.0:
        return fit_quantile_threshold(x.ravel(), fpr_target=fpr_target), best_k
    try:
        shape, loc, scale = stats.gamma.fit(top_samples)
        tau = float(stats.gamma.ppf(level, shape, loc=loc, scale=scale))
    except (ValueError, RuntimeError):
        return fit_quantile_threshold(x.ravel(), fpr_target=fpr_target), best_k
    return tau, best_k
