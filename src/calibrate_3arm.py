"""3-arm calibration on clean-validation scores only (Phase C).

Arm A: empirical quantile. Arm B: GMM (+Gamma). Arm C: MOM-SPOT with guardrail.
2-of-3 stability vote + recall-first veto. Never fit on train. Never score test.
"""

import numpy as np


def fit_quantile_threshold(scores_clean: np.ndarray, *, fpr_target: float = 0.01) -> float:
    """Empirical-quantile threshold: flag the top `fpr_target` fraction of clean scores."""
    return float(np.quantile(np.asarray(scores_clean, dtype=float), 1.0 - fpr_target))
