"""Apply 3-arm calibration + shrunk Chair-Varshney fusion to OOF scores.

Pipeline per expert: arm thresholds on clean-val OOF scores -> stability vote ->
binary decisions. Per family: Laplace-smoothed reliabilities shrunk to global,
CV-weighted vote -> fused score. Per-class max-F1 thresholds on fused scores ->
final decisions, with recall-first veto for protected families/ids.

Optimism caveat (registry): thresholds are tuned AND evaluated on OOF (no
held-out test exists yet) — reported numbers are validation, not test.
"""

from __future__ import annotations

import numpy as np
import pandas as pd  # type: ignore[import-untyped]

from src.calibrate_3arm import (
    apply_recall_veto,
    fit_gmm_threshold,
    fit_pot_mom_threshold,
    fit_quantile_threshold,
    stability_vote,
)
from src.fusion import cv_weights, estimate_reliabilities
from src.train_pipeline import pick_per_class_thresholds


def expert_threshold(clean_scores: np.ndarray) -> float:
    """2-of-3 vote threshold from the three arms on clean-val scores."""
    s = np.asarray(clean_scores, dtype=float)
    s = s[np.isfinite(s)]
    tau_a = fit_quantile_threshold(s)
    tau_b, _ = fit_gmm_threshold(s)
    q95 = float(np.quantile(s, 0.95))
    exc = s[s > q95] - q95
    tau_c = fit_pot_mom_threshold(exc, prior_zq=tau_a)["z_q"]
    return stability_vote(tau_a, tau_b, tau_c)


def apply_calibration(
    oof: pd.DataFrame,
    score_cols: list[str],
    *,
    clean_mask,
    families,
    ids=None,
    protected: tuple = ("F-06", "F-12", "F-14"),
) -> pd.DataFrame:
    """Fuse expert OOF scores into per-row final decisions."""
    fam = np.asarray(families)
    y = oof["y"].to_numpy(dtype=int)
    clean = np.asarray(clean_mask, dtype=bool)
    decisions: dict[str, np.ndarray] = {}
    for col in score_cols:
        s = oof[col].to_numpy(dtype=float)
        tau = expert_threshold(s[clean])
        decisions[col] = s > tau
    # Global reliabilities (pooled OOF) + per-family shrinkage.
    out = oof.copy()
    fused = np.zeros(len(oof))
    for f in sorted(set(fam.tolist())):
        rows = np.flatnonzero(fam == f)
        row_score = np.zeros(len(rows))
        for col in score_cols:
            d = decisions[col][rows]
            tp = int((d & (y[rows] == 1)).sum())
            fp = int((d & (y[rows] == 0)).sum())
            p = int((y[rows] == 1).sum())
            n = int((y[rows] == 0).sum())
            gtp = int((decisions[col] & (y == 1)).sum())
            gfp = int((decisions[col] & (y == 0)).sum())
            gp, gn = int((y == 1).sum()), int((y == 0).sum())
            pd_hat, pfa_hat = estimate_reliabilities(tp, fp, p, n)
            g_pd, g_pfa = estimate_reliabilities(gtp, gfp, gp, gn)
            lam = len(rows) / (len(rows) + 20)
            pd_s = lam * pd_hat + (1 - lam) * g_pd
            pfa_s = lam * pfa_hat + (1 - lam) * g_pfa
            w_pos, w_neg = cv_weights(pd_s, pfa_s)
            row_score += np.where(d, w_pos, w_neg)
        fused[rows] = row_score
    out["fused_score"] = fused
    thr = pick_per_class_thresholds(fused, y, fam)
    final = np.array([fused[i] >= thr[str(fam[i])] for i in range(len(oof))])
    for f in sorted(set(fam.tolist())):
        rows_f = fam == f
        final[rows_f] = apply_recall_veto(final[rows_f], str(f), protected=protected)
    if ids is not None:
        id_arr = np.asarray(ids)
        final[np.array([v in protected for v in id_arr])] = True
    out["fused"] = final
    return out
