"""3-arm calibration on clean-validation scores only (Phase C).

Arm A: empirical quantile. Arm B: GMM (+Gamma). Arm C: MOM-SPOT with guardrail.
2-of-3 stability vote + recall-first veto. Never fit on train. Never score test.
"""

import numpy as np
from scipy import stats  # type: ignore[import-untyped]
from sklearn.mixture import GaussianMixture  # type: ignore[import-untyped]


def fit_quantile_threshold(
    scores_clean: np.ndarray, *, fpr_target: float = 0.01
) -> float:
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
    # BIC over K beyond the distinct-value count is degenerate (k-means init
    # warns/fails on duplicate points); cap K at the distinct count.
    k_cap = max(1, min(max_components, len(np.unique(x))))
    best_k, best_bic = 1, GaussianMixture(n_components=1, random_state=0).fit(x).bic(x)
    for k in range(2, k_cap + 1):
        bic = GaussianMixture(n_components=k, random_state=0).fit(x).bic(x)
        if bic < best_bic:
            best_k, best_bic = k, bic
    gm = GaussianMixture(n_components=best_k, random_state=0).fit(x)
    top = int(np.argmax(gm.means_.ravel()))
    top_samples = x[gm.predict(x) == top].ravel()
    level = 1.0 - fpr_target * n / max(top_samples.size, 1)
    if (
        top_samples.size <= fpr_target * n
        or not 0.0 < level < 1.0
        or float(np.var(top_samples)) == 0.0
    ):
        return fit_quantile_threshold(x.ravel(), fpr_target=fpr_target), best_k
    try:
        shape, loc, scale = stats.gamma.fit(top_samples)
        tau = float(stats.gamma.ppf(level, shape, loc=loc, scale=scale))
    except (ValueError, RuntimeError):
        return fit_quantile_threshold(x.ravel(), fpr_target=fpr_target), best_k
    return tau, best_k


MIN_EXCESSES_FOR_REFIT = 20
XI_CLIP = (-0.5, 0.5)
# MOM xi_hat is algebraically bounded above by one half, so the existence
# boundary itself is unreachable in-sample; MOM small-sample SE is ~0.1-0.2
# (Hosking-Wallis; Mackay grid), making degraded-band estimates
# statistically indistinguishable from the variance-undefined regime.
XI_DEGRADED = 9 / 20  # degraded-band edge


def fit_pot_mom_threshold(
    excesses: np.ndarray,
    *,
    level: float = 0.97,
    risk_q: float = 1e-3,
    prior_zq: float | None = None,
) -> dict:
    """MOM-SPOT threshold with 5-rule guardrail (excesses = scores above the POT level).

    1. Refit gate: N_t < 20 -> freeze (keep prior z_q, flag fallback).
    2. MOM invalid at xi >= 0.5 (variance undefined) -> freeze + clip + flag.
    3. Hard-clip xi_hat to (-0.5, 0.5); log the clip.
    4. Endpoint feasibility (xi < 0): reject fits whose implied upper bound
       excludes observed excesses.
    5. Contamination freeze is a caller contract: never pass flagged-anomaly
       excesses into a refit.
    Full Grimshaw-MLE deferred: MOM+clip is the streaming arm; revisit only
    if Arm C miscalibrates on clean-val (see verification-economics).
    """
    y = np.asarray(excesses, dtype=float).ravel()
    n_t = y.size
    frozen = {
        "z_q": prior_zq
        if prior_zq is not None
        else float(np.max(y))
        if n_t
        else float("inf")
    }
    if n_t < MIN_EXCESSES_FOR_REFIT:
        return {
            "z_q": frozen["z_q"],
            "xi_hat": 0.0,
            "sigma_hat": 0.0,
            "n_excesses": n_t,
            "fallback_fired": True,
            "clip_logged": False,
        }
    mean, var = float(np.mean(y)), float(np.var(y, ddof=1))
    if not np.isfinite(mean) or not np.isfinite(var) or var <= 0 or mean <= 0:
        return {
            "z_q": frozen["z_q"],
            "xi_hat": 0.0,
            "sigma_hat": 0.0,
            "n_excesses": n_t,
            "fallback_fired": True,
            "clip_logged": False,
        }
    xi_raw = 0.5 * (1.0 - mean**2 / var)
    sigma_raw = mean * (1.0 - xi_raw)
    if xi_raw >= XI_DEGRADED:
        return {
            "z_q": frozen["z_q"],
            "xi_hat": float(np.clip(xi_raw, *XI_CLIP)),
            "sigma_hat": sigma_raw,
            "n_excesses": n_t,
            "fallback_fired": True,
            "clip_logged": True,
        }
    if xi_raw < 0 and -sigma_raw / xi_raw < float(np.max(y)):
        return {
            "z_q": frozen["z_q"],
            "xi_hat": float(np.clip(xi_raw, *XI_CLIP)),
            "sigma_hat": sigma_raw,
            "n_excesses": n_t,
            "fallback_fired": True,
            "clip_logged": True,
        }
    clip_logged = False
    if not XI_CLIP[0] < xi_raw < XI_CLIP[1]:
        xi_raw = float(np.clip(xi_raw, *XI_CLIP))
        clip_logged = True
    xi_hat, sigma_hat = xi_raw, mean * (1.0 - xi_raw)
    rate = 1.0 - level
    if abs(xi_hat) < 1e-6:
        z_q = -sigma_hat * np.log(risk_q / rate)
    else:
        z_q = sigma_hat / xi_hat * ((risk_q / rate) ** (-xi_hat) - 1.0)
    fallback_fired = clip_logged or not np.isfinite(z_q) or z_q <= 0
    return {
        "z_q": frozen["z_q"] if fallback_fired and prior_zq is not None else float(z_q),
        "xi_hat": xi_hat,
        "sigma_hat": sigma_hat,
        "n_excesses": n_t,
        "fallback_fired": fallback_fired,
        "clip_logged": clip_logged,
    }


def stability_vote(
    tau_a: float,
    tau_b: float,
    tau_c: float,
    *,
    f1_tol: float = 0.02,
    fp_tol: float = 3 / 1000,
) -> float:
    """2-of-3 vote: median of the closest pair; all-disagree -> most conservative (max).

    `f1_tol`/`fp_tol` are the Task-9 stability-report tolerances (arm agreement
    is adjudicated there against predicted F1/FP deltas); the vote itself uses a
    relative disagree rule — closest spread above 25% of the three-median means
    no pair agrees.
    """
    taus = sorted([float(tau_a), float(tau_b), float(tau_c)])
    spreads = [
        (taus[1] - taus[0], (taus[0] + taus[1]) / 2.0),
        (taus[2] - taus[1], (taus[1] + taus[2]) / 2.0),
    ]
    best_spread, best_mid = min(spreads, key=lambda s: s[0])
    if best_spread > 0.25 * float(np.median(taus)):
        return taus[2]
    return best_mid


PROTECTED_FAMILIES = ("F-06", "F-12", "F-14")


def apply_recall_veto(
    flags: np.ndarray, family: str, *, protected: tuple = PROTECTED_FAMILIES
) -> np.ndarray:
    """Recall-first veto: protected families always alarm (recall 1.0, never
    traded for FAR); all other families pass through for downstream veto logic."""
    out = np.asarray(flags, dtype=bool).copy()
    if family in protected:
        out[:] = True
    return out
