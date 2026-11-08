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
    "stale_rate_W",
    "tput_stall_W",
    "var_ratio_W",
    "slope_persist_W",
    "combo_loss",
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
    # In-fold synthetic injection (train-only): when minority is scarce,
    # top up with COE swaps + IQR point outliers (both label injected rows 1).
    if 0 < int((y == 1).sum()) < 0.2 * len(y):
        from src.augment import coe_swap, point_outliers

        rng = np.random.default_rng(0)
        x, y = coe_swap(x, y, rng=rng, frac=0.10)
        x, y = point_outliers(x, y, rng=rng, n=max(4, int(0.05 * len(y))))
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


def add_state_features(df: pd.DataFrame, *, w: int = 16) -> pd.DataFrame:
    """Causal trailing state features per episode (no future leakage).

    - stale_rate_W: trailing rate of stale_hold_run>0 (survives interrupted bursts).
    - tput_stall_W: trailing max of cycle_lag (stall depth).
    - var_ratio_W: trailing variance of max-deviation projection / episode median.
    - slope_persist_W: trailing run of same-sign first differences (drift persistence).
    - combo_loss: (cycle_lag>=5) & (stale_hold_run>=1) persisted corroboration bit.
    Missing inputs degrade to zeros (v6 contract may lack cols in tiny tests).
    """
    out = df.copy()
    n = len(out)
    stale = (
        out["stale_hold_run"].to_numpy(dtype=float)
        if "stale_hold_run" in out
        else np.zeros(n)
    )
    lag = out["cycle_lag"].to_numpy(dtype=float) if "cycle_lag" in out else np.zeros(n)
    obs_cols = [c for c in out.columns if c.startswith("obs_")]
    if obs_cols:
        med = out[obs_cols].median().to_numpy(dtype=float)
        proj = np.abs(out[obs_cols].to_numpy(dtype=float) - med).max(axis=1)
    else:
        proj = np.zeros(n)
    stale_rate = np.zeros(n)
    stall = np.zeros(n)
    var_ratio = np.zeros(n)
    slope = np.zeros(n)
    for _, g in out.groupby("episode_id", sort=False):
        idx = g.index.to_numpy()
        m = len(idx)
        st = (
            (g["stale_hold_run"].to_numpy(dtype=float) > 0).astype(float)
            if "stale_hold_run" in g
            else np.zeros(m)
        )
        lg = g["cycle_lag"].to_numpy(dtype=float) if "cycle_lag" in g else np.zeros(m)
        pr = proj[g.index]
        sr = np.array([st[max(0, i - w + 1) : i + 1].mean() for i in range(m)])
        tm = np.array([lg[max(0, i - w + 1) : i + 1].max() for i in range(m)])
        vr = np.zeros(m)
        for i in range(m):
            seg = pr[max(0, i - w + 1) : i + 1]
            vr[i] = float(np.var(seg)) if len(seg) > 1 else 0.0
        base = float(np.median(vr)) if m else 0.0
        vr = vr / (base + 1e-9)
        d = np.sign(np.diff(pr, prepend=pr[0] if m else 0.0))
        run = np.zeros(m)
        for i in range(1, m):
            run[i] = (
                run[i - 1] + 1
                if d[i] != 0 and d[i] == d[i - 1]
                else (1.0 if d[i] != 0 else 0.0)
            )
            if run[i] > w:
                run[i] = float(w)
        stale_rate[idx] = sr
        stall[idx] = np.minimum(tm, 255.0)
        var_ratio[idx] = vr
        slope[idx] = run
    out["stale_rate_W"] = stale_rate
    out["tput_stall_W"] = stall
    out["var_ratio_W"] = var_ratio
    out["slope_persist_W"] = slope
    out["combo_loss"] = ((lag >= 5) & (stale >= 1)).astype(float)
    return out


def train_oof_subset(
    n_episodes: int, n_splits: int, out: str, parquet: str = PARQUET
) -> pd.DataFrame:
    """OOF over the first n_episodes (fast contract probe)."""
    df = pd.read_parquet(parquet)
    eps = sorted(df["episode_id"].unique())[:n_episodes]
    sub = df[df["episode_id"].isin(eps)].reset_index(drop=True)
    sub = add_state_features(sub)
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
    df = add_state_features(df)
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
