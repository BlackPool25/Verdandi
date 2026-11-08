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
from src.fusion import estimate_reliabilities
from src.train_pipeline import (
    compute_raw_pointwise_f1,
    pick_per_class_thresholds,
)


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
    window_mask=None,
    protected: tuple = ("F-06", "F-12", "F-14"),
) -> pd.DataFrame:
    """Fuse expert OOF scores into per-row final decisions.

    Scores are z-normalized per episode first (transportability: a locked
    threshold cannot hold FPR when episode baselines drift). Veto is scoped:
    protected families force whole-slice True; protected IDS force True only
    inside window_mask (root windows), never whole-episode.
    """
    fam = np.asarray([str(v) for v in families])
    y = oof["y"].to_numpy(dtype=int)
    clean = np.asarray(clean_mask, dtype=bool)
    normed: dict[str, np.ndarray] = {}
    for col in score_cols:
        s = oof[col].to_numpy(dtype=float)
        med = oof.groupby("episode_id")[col].transform("median").to_numpy(dtype=float)
        q75 = oof.groupby("episode_id")[col].transform(lambda x: float(np.quantile(x, 0.75))).to_numpy(dtype=float)
        q25 = oof.groupby("episode_id")[col].transform(lambda x: float(np.quantile(x, 0.25))).to_numpy(dtype=float)
        iqr = np.maximum(q75 - q25, 1e-9)
        normed[col] = np.where(np.isfinite(s), (s - med) / iqr, 0.0)
    decisions: dict[str, np.ndarray] = {}
    for col in score_cols:
        s = normed[col]
        tau = expert_threshold(s[clean])
        decisions[col] = s > tau
    # Global reliabilities (pooled OOF) + per-family shrinkage. Weights come
    # from hard decisions; the fused SCORE is soft (z-scored per expert on
    # clean val, weighted by shrunk informedness) so ranking info survives.
    out = oof.copy()
    z: dict[str, np.ndarray] = {}
    for col in score_cols:
        s = normed[col]
        sc = s[clean]
        sc = sc[np.isfinite(sc)]
        med = float(np.median(sc)) if sc.size else 0.0
        iqr = float(np.quantile(sc, 0.75) - np.quantile(sc, 0.25)) if sc.size else 1.0
        iqr = iqr or 1.0
        z[col] = (s - med) / (iqr + 1e-9)
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
            j_fam = pd_hat - pfa_hat
            j_glob = g_pd - g_pfa
            w = max(0.0, lam * j_fam + (1 - lam) * j_glob)
            row_score += w * z[col][rows]
        fused[rows] = row_score
    out["fused_score"] = fused
    thr = pick_per_class_thresholds(fused, y, fam)
    final = np.zeros(len(oof), dtype=bool)
    for f in sorted(set(fam.tolist())):
        rows = np.flatnonzero(fam == f)
        dec = fused[rows] >= thr[str(f)]
        # Trivial-guard: max-F1 on uninformative scores degenerates to flag-all
        # (F1(all-true) = 2*pi/(1+pi) beats F1(none) = 0). Precision-first: when
        # the operating point cannot beat trivial by a material 2pp, abstain.
        prev = float(y[rows].mean()) if len(rows) else 0.0
        trivial = 2 * prev / (1 + prev) if prev > 0 else 0.0
        achieved = compute_raw_pointwise_f1(y[rows], dec.astype(int))
        final[rows] = dec if achieved >= trivial + 0.02 else False
    for f in sorted(set(fam.tolist())):
        rows_f = fam == f
        final[rows_f] = apply_recall_veto(final[rows_f], str(f), protected=protected)
    if ids is not None:
        id_arr = np.asarray(ids).astype(str)
        hit = np.isin(id_arr, list(protected))
        if window_mask is not None:
            hit &= np.asarray(window_mask, dtype=bool)
        final[hit] = True
    out["fused"] = final
    return out
