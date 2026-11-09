"""Supervised window dataset (max-quality track).

Windows aggregate step rows into fixed-length feature vectors: per-obs-channel
[mean, std, min, max, end-start slope] plus structural [stall depth, stale
rate, reject/degrade max]. Labels are window-level: y=1 iff any step in the
window is faulty (detection = does this window contain fault). All features
are window-internal (causal by construction); groups = episode_id for
GroupKFold (no episode leakage).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

STRUCT_COLS = ("cycle_lag", "stale_hold_run", "reject_flag_count", "degrade_flag_count")


def n_obs_features(n_obs_cols: int) -> int:
    """Width of the obs block: 5 stats per channel, emitted first."""
    return 5 * n_obs_cols


def fit_clean_norm(
    X: np.ndarray, y: np.ndarray, n_obs: int
) -> tuple[np.ndarray, np.ndarray]:
    """Median/IQR of the obs block on clean rows only (caller passes train-only).

    Inter-machine level/scale differences live here; fault signatures survive
    as deviations from the clean baseline instead of raw machine units.
    """
    xc = X[np.asarray(y) == 0][:, :n_obs]
    med = np.median(xc, axis=0)
    iqr = np.maximum(
        np.quantile(xc, 0.75, axis=0) - np.quantile(xc, 0.25, axis=0), 1e-9
    )
    return np.asarray(med, dtype=float), np.asarray(iqr, dtype=float)


def apply_norm(
    X: np.ndarray, med: np.ndarray, iqr: np.ndarray, n_obs: int
) -> np.ndarray:
    """Normalize the obs block; structural counters pass through untouched."""
    out = np.array(X, dtype=float)
    out[:, :n_obs] = (out[:, :n_obs] - med) / iqr
    return out


def _window_features(seg: pd.DataFrame, obs_cols: list[str]) -> np.ndarray:
    parts = []
    for c in obs_cols:
        v = seg[c].to_numpy(dtype=float)
        parts += [v.mean(), v.std(), v.min(), v.max(), v[-1] - v[0]]
    for c in STRUCT_COLS:
        if c not in seg:
            parts += [0.0, 0.0]
            continue
        v = seg[c].to_numpy(dtype=float)
        if c == "stale_hold_run":
            parts += [float((v > 0).mean()), float(v.max())]
        elif c == "cycle_lag":
            parts += [float(v.max()), float(v.mean())]
        else:
            parts += [float(v.max()), float(v.mean())]
    return np.array(parts, dtype=float)


INVARIANT_STATS = ("max", "mean", "spread")


def _window_features_invariant(seg: pd.DataFrame, obs_cols: list[str]) -> np.ndarray:
    """Origin-invariant window features: no channel identity survives.

    Absolute per-channel stats let the GBM key on *which* machine moved — with
    26 origins and thin per-cell coverage that memorizes instead of learning.
    These summaries (max/mean/spread across channels, per stat) fire on
    deviation *anywhere*, at the cost of losing which-machine information
    (detection does not need it). Fold-fit clean normalization (applied later
    at window level) puts them in comparable units.
    """
    mat = np.stack([seg[c].to_numpy(dtype=float) for c in obs_cols], axis=1)
    stats = np.stack(
        [
            mat.mean(axis=0),
            mat.std(axis=0),
            mat.min(axis=0),
            mat.max(axis=0),
            mat[-1] - mat[0],
        ],
        axis=1,
    )  # [n_chan, 5]
    parts = []
    for j in range(stats.shape[1]):
        col = stats[:, j]
        parts += [float(col.max()), float(col.mean()), float(col.std())]
    out = np.array(parts, dtype=float)
    struct = _window_features(seg, [])[-8:]
    return np.concatenate([out, struct])


def build_windows(
    df: pd.DataFrame,
    *,
    w: int = 32,
    stride: int = 8,
    invariant: bool = False,
    offset: int = 0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Slide windows over each episode; return (X, y, fam, groups).

    invariant=True emits origin-invariant features (no channel identity).
    offset shifts the grid phase (streaming inference never aligns to the
    training grid; offset=stride//2 is the worst case to test).
    """
    if w < 1:
        raise ValueError(f"w must be >= 1, got {w}")
    if stride < 1:
        raise ValueError(f"stride must be >= 1, got {stride}")
    obs_cols = [c for c in df.columns if c.startswith("obs_")]
    xs, ys, fams, groups = [], [], [], []
    for ep, g in df.groupby("episode_id", sort=False):
        g = g.sort_values("step").reset_index(drop=True)
        yv = g["y"].to_numpy(dtype=int)
        famv = (
            g["fault_family"].to_numpy()
            if "fault_family" in g
            else np.array(["none"] * len(g))
        )
        for s in range(offset, len(g) - w + 1, stride):
            seg = g.iloc[s : s + w]
            xs.append(
                _window_features_invariant(seg, obs_cols)
                if invariant
                else _window_features(seg, obs_cols)
            )
            win_y = yv[s : s + w]
            ys.append(int(win_y.any()))
            ff = famv[s : s + w][win_y == 1]
            fams.append(str(ff[0]) if len(ff) else "none")
            groups.append(ep)
    return np.array(xs), np.array(ys), np.array(fams), np.array(groups)
