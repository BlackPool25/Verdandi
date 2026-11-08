#!/usr/bin/env python3
"""Train/evaluate tabular OOF experts + supervised S-arm on v6 step rows.

N-arm (unsupervised, clean-fit): knn/pca/lof. S-arm (supervised):
balanced LogisticRegression on all train rows (class_weight='balanced' +
focal confidence weights; labels allowed — it IS the supervised arm).
All scores out-of-fold via src.oof (fold-only normalization, blind episodes).
"""

from __future__ import annotations

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd  # type: ignore[import-untyped]

from src import config
from src.oof import run_oof
from src.train_pipeline import as_abnormal_scores

STRUCT_FEATURES = [
    "cycle_lag",
    "down_run",
    "dwell_steps",
    "stale_hold_run",
    "reject_flag_count",
    "degrade_flag_count",
    "buffer_occ",
    "state_hist_delta",
]

FEATURE_CHANNELS = list(config.MACHINE_NAMES) + STRUCT_FEATURES
PARQUET = "artifacts/m0b_v6.parquet"
OOF_OUT = "artifacts/m0b_oof_scores.parquet"


def _unsupervised(name: str, ctor, **kwargs):
    def maker(x_train: np.ndarray, y_train: np.ndarray):
        clf = ctor(**kwargs).fit(np.asarray(x_train)[np.asarray(y_train) == 0])
        return lambda x: as_abnormal_scores(name, clf, np.asarray(x, dtype=float))

    return maker


def _supervised_lr(x_train: np.ndarray, y_train: np.ndarray):
    from sklearn.linear_model import LogisticRegression  # type: ignore[import-untyped]

    from src.train_pipeline import compute_sample_weights, focal_confidence_weights

    x = np.asarray(x_train, dtype=float)
    y = np.asarray(y_train, dtype=int)
    # shortcut: no synthetic injection — measured ~zero gain in-sample and adds
    # label noise; revisit only with per-family recall evidence on weak families.
    clf = LogisticRegression(class_weight="balanced", max_iter=500).fit(x, y)
    # Focal confidence weights recorded for the weighted-loss path (kept as
    # sample weights here so hard minority rows train louder).
    try:
        p_true = np.asarray(clf.predict_proba(x), dtype=float)[np.arange(len(y)), y]
        w = compute_sample_weights(y) * (focal_confidence_weights(p_true) + 0.5)
        clf = LogisticRegression(class_weight="balanced", max_iter=500).fit(
            x, y, sample_weight=w
        )
    except ValueError:
        pass
    return lambda x_: np.asarray(clf.decision_function(np.asarray(x_, dtype=float)))


def makers() -> dict:
    from sklearn.decomposition import PCA  # type: ignore[import-untyped]
    from sklearn.neighbors import (  # type: ignore[import-untyped]
        LocalOutlierFactor,
        NearestNeighbors,
    )

    return {
        "knn": _unsupervised("knn", NearestNeighbors, n_neighbors=5),
        "pca": _unsupervised("pca", PCA, n_components=0.90),
        "lof": _unsupervised("lof", LocalOutlierFactor, n_neighbors=20, novelty=True),
        "supervised_lr": _supervised_lr,
    }


def train_oof_subset(
    n_episodes: int, n_splits: int, out: str, parquet: str = PARQUET
) -> pd.DataFrame:
    """OOF over the first n_episodes (fast contract probe)."""
    df = pd.read_parquet(parquet)
    eps = sorted(df["episode_id"].unique())[:n_episodes]
    sub = df[df["episode_id"].isin(eps)].reset_index(drop=True)
    scored = run_oof(sub, FEATURE_CHANNELS, makers(), n_splits=n_splits)
    scored = add_temporal(scored, [c for c in sub.columns if c.startswith("obs_")])
    pathlib.Path(out).parent.mkdir(parents=True, exist_ok=True)
    scored.to_parquet(out)
    return scored


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="tabular OOF experts + S-arm, full battery"
    )
    ap.add_argument("--parquet", default=PARQUET)
    ap.add_argument("--out", default=OOF_OUT)
    ap.add_argument("--n-splits", type=int, default=5)
    args = ap.parse_args(argv)
    df = pd.read_parquet(args.parquet)
    scored = run_oof(df, FEATURE_CHANNELS, makers(), n_splits=args.n_splits)
    scored = add_temporal(scored, [c for c in df.columns if c.startswith("obs_")])
    pathlib.Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    scored.to_parquet(args.out)
    print(f"rows={len(scored)} experts={sorted(makers())} -> {args.out}")
    return 0


def add_temporal(df: pd.DataFrame, obs_cols: list[str]) -> pd.DataFrame:
    """Per-episode causal temporal scores.

    DLinear: least-squares trend per obs channel fit on pre-root steps only
    (steps before the first y==1; fault starts at t0 by construction, so no
    label leakage — the fit never sees post-root data). Score = max abs residual.
    MP guardrail: stumpy discord of the episode's max-deviation series confirms
    (within +-m) the DLinear peak step.
    """
    import stumpy  # type: ignore[import-untyped]

    from src.train_pipeline import fit_dlinear_trend

    out = df.copy()
    dlinear = np.full(len(df), np.nan)
    confirm = np.zeros(len(df), dtype=bool)
    for _, g in df.groupby("episode_id", sort=False):
        idx = g.index.to_numpy()
        x = g[obs_cols].to_numpy(dtype=float)
        y = g["y"].to_numpy(dtype=int)
        first = np.flatnonzero(y == 1)
        pre = np.arange(len(g)) if first.size == 0 else np.arange(int(first[0]))
        if pre.size < 2:
            pre = np.arange(len(g))
        coef = fit_dlinear_trend(x[pre])
        t = np.arange(len(g), dtype=float)[:, None]
        resid = np.abs(x - (t * coef[0] + coef[1])).max(axis=1)
        dlinear[idx] = resid
        proj = np.abs(x - np.median(x, axis=0)).max(axis=1)
        m = int(min(64, max(8, len(g) // 4)))
        if len(g) > m:
            mp = stumpy.stump(proj, m=m)
            discord = int(np.argmax(np.asarray(mp.P_, dtype=float)))
            peak = int(np.argmax(resid))
            if abs(discord - peak) <= m:
                confirm[idx] = True
    out["dlinear"] = dlinear
    out["mp_confirm"] = confirm
    return out


if __name__ == "__main__":
    raise SystemExit(main())
