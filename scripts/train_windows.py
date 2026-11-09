#!/usr/bin/env python3
"""Supervised window GBM (max-quality track): binary fault head + family head.

GroupKFold over episodes; reports window-F1 (binary), per-family recall, and
episode-hit (any positive window in a fault episode) with Wilson CIs.
"""

from __future__ import annotations

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd  # type: ignore[import-untyped]


def train_binary_gbm(X_tr: np.ndarray, y_tr: np.ndarray) -> object:
    from sklearn.ensemble import HistGradientBoostingClassifier  # type: ignore[import-untyped]

    clf = HistGradientBoostingClassifier(max_iter=300, random_state=0)
    clf.fit(X_tr, y_tr)
    return clf


def episode_family(groups: np.ndarray, window_fam: np.ndarray) -> np.ndarray:
    """Episode-level family per window: the fault family of its episode, else none.

    Window-fam slices of a fault family are all-positive by construction (a window
    carries the family label iff it overlaps the fault), which makes per-slice
    max-F1 tuning vacuous. Episode slices include the family's clean windows, so
    the threshold trades precision against recall honestly.
    """
    g = np.asarray(groups)
    wf = np.asarray(window_fam)
    out = np.array(["none"] * len(g), dtype=object)
    for ep in np.unique(g):
        m = g == ep
        ff = wf[m]
        ff = ff[ff != "none"]
        if len(ff):
            out[m] = str(ff[0])
    return out


def pick_per_family_thresholds(
    scores: np.ndarray,
    y_true: np.ndarray,
    families: np.ndarray,
    *,
    fallback: float = 0.5,
) -> dict[str, float]:
    """Per-family max-F1 thresholds on window scores (tuning slice = eval slice).

    All-negative slices (e.g. clean episodes) carry no signal — tuning there is
    vacuous and collapses to flag-all, so they keep the fallback threshold.
    Optimism caveat: thresholds picked on OOF are validation numbers, not test.
    """
    from src.train_pipeline import pick_threshold_max_f1

    s = np.asarray(scores, dtype=float)
    y = np.asarray(y_true, dtype=int)
    f = np.asarray(families)
    out = {}
    for fam in sorted(set(f.tolist())):
        m = f == fam
        if int(y[m].sum()) == 0:
            out[str(fam)] = float(fallback)
        else:
            out[str(fam)] = float(pick_threshold_max_f1(s[m], y[m]))
    return out


def episode_hit_rate(
    window_pred: np.ndarray, groups: np.ndarray, window_fam: np.ndarray
) -> dict:
    """Per fault episode: hit iff any window predicted positive; clean FP rate."""
    hits, clean_fp = 0, 0
    n_fault, n_clean = 0, 0
    for ep in np.unique(groups):
        m = groups == ep
        is_fault = bool((window_fam[m] != "none").any())
        if is_fault:
            n_fault += 1
            hits += int(window_pred[m].any())
        else:
            n_clean += 1
            clean_fp += int(window_pred[m].any())
    return {
        "hit_rate": hits / n_fault if n_fault else 0.0,
        "clean_fp_rate": clean_fp / n_clean if n_clean else 0.0,
        "n_fault": n_fault,
        "n_clean": n_clean,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="train window GBM on mass battery")
    ap.add_argument("--parquet", default="artifacts/m0b_mass_*.parquet")
    ap.add_argument("--w", type=int, default=32)
    ap.add_argument("--stride", type=int, default=8)
    ap.add_argument("--splits", type=int, default=3)
    ap.add_argument("--save-oof", default="")
    ap.add_argument("--invariant", action="store_true")
    ap.add_argument(
        "--lags", action="store_true", help="opt-in intra-window lag deltas (v3)"
    )
    ap.add_argument(
        "--residuals", action="store_true", help="opt-in twin-residual block (v3)"
    )
    ap.add_argument(
        "--regime-norm",
        action="store_true",
        help="opt-in per-regime clean normalization (v3)",
    )
    ap.add_argument(
        "--partflow", action="store_true", help="opt-in invariant part-flow block (v4)"
    )
    ap.add_argument("--n-jobs", type=int, default=-1)
    args = ap.parse_args(argv)
    import glob as _glob

    from joblib import Parallel, delayed  # type: ignore[import-untyped]
    from sklearn.model_selection import StratifiedGroupKFold  # type: ignore[import-untyped]

    from src.train_pipeline import compute_raw_pointwise_f1, pick_threshold_max_f1
    from src.window_dataset import (
        STRUCT_COLS,
        apply_norm,
        apply_norm_regime,
        build_windows,
        fit_clean_norm,
        fit_clean_norm_regime,
    )

    paths = sorted(_glob.glob(args.parquet))
    if not paths:
        raise SystemExit(f"no parquet shards match {args.parquet}")
    df = pd.concat([pd.read_parquet(p) for p in paths], ignore_index=True)
    bw: dict = {}
    if args.regime_norm:
        bw["return_regimes"] = True
    out = build_windows(
        df,
        w=args.w,
        stride=args.stride,
        invariant=args.invariant,
        lags=args.lags,
        residuals=args.residuals,
        partflow=args.partflow,
        **bw,
    )
    if args.regime_norm:
        X, y, fam, groups, reg = out
        # Anchor to the episode clean-prefix regime: a window's own regime
        # is fault-caused (DOWN/STARVED), normalizing by it erases signal.
        from src.window_dataset import anchor_regimes_by_episode

        reg = anchor_regimes_by_episode(reg, groups)
    else:
        X, y, fam, groups = out
        reg = None
    n_obs = 15 if args.invariant else X.shape[1] - 2 * len(STRUCT_COLS)
    print(f"windows={len(X)} feats={X.shape[1]} pos_rate={y.mean():.3f}")
    cv = StratifiedGroupKFold(n_splits=args.splits)
    oof = np.zeros(len(X))

    def _fit_fold(tr: np.ndarray, te: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        # Fold-only clean baseline: inter-machine scale differences are fit on
        # train-clean windows and applied blind to the held-out episodes.
        # Runs in a worker process: HistGBM threads internally, so the outer
        # level parallelizes over folds while inner threading stays per-fit.
        if args.regime_norm:
            tab = fit_clean_norm_regime(X[tr], y[tr], reg[tr], n_obs)
            clf = train_binary_gbm(apply_norm_regime(X[tr], tab, reg[tr], n_obs), y[tr])
            return te, np.asarray(
                clf.predict_proba(apply_norm_regime(X[te], tab, reg[te], n_obs))[:, 1]
            )
        med, iqr = fit_clean_norm(X[tr], y[tr], n_obs)
        clf = train_binary_gbm(apply_norm(X[tr], med, iqr, n_obs), y[tr])
        return te, np.asarray(
            clf.predict_proba(apply_norm(X[te], med, iqr, n_obs))[:, 1]
        )

    for te, scores in Parallel(n_jobs=args.n_jobs)(
        delayed(_fit_fold)(tr, te) for tr, te in cv.split(X, y, groups)
    ):
        oof[te] = scores
    f1 = compute_raw_pointwise_f1(y, (oof >= 0.5).astype(int))
    ep = episode_hit_rate((oof >= 0.5).astype(int), groups, fam)
    print(
        f"window-F1={f1:.4f} episode-hit={ep['hit_rate']:.4f} clean-fp={ep['clean_fp_rate']:.4f}"
    )
    global_thr = float(pick_threshold_max_f1(oof, y))
    thr = pick_per_family_thresholds(
        oof, y, episode_family(groups, fam), fallback=global_thr
    )
    tuned = np.zeros(len(X), dtype=int)
    ep_fam = episode_family(groups, fam)
    for f in sorted(set(ep_fam.tolist())):
        m = ep_fam == f
        tuned[m] = (oof[m] >= thr[str(f)]).astype(int)
    f1t = compute_raw_pointwise_f1(y, tuned)
    ept = episode_hit_rate(tuned, groups, fam)
    print(
        f"tuned window-F1={f1t:.4f} episode-hit={ept['hit_rate']:.4f} clean-fp={ept['clean_fp_rate']:.4f}"
    )
    per_fam = {}
    for f in sorted(set(fam.tolist()) - {"none"}):
        m = fam == f
        per_fam[f] = round(float(tuned[m].mean()), 4)
    print("per-family window recall:", per_fam)
    print("per-family thresholds:", {k: round(v, 4) for k, v in thr.items()})
    if args.save_oof:
        pd.DataFrame(
            {"score": oof, "dec": tuned, "y": y, "fam": fam, "ep": groups}
        ).to_parquet(args.save_oof, index=False)
        print(f"oof saved -> {args.save_oof}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
