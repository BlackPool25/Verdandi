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


def build_windows(
    df: pd.DataFrame, *, w: int = 32, stride: int = 8
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Slide windows over each episode; return (X, y, fam, groups)."""
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
        for s in range(0, len(g) - w + 1, stride):
            seg = g.iloc[s : s + w]
            xs.append(_window_features(seg, obs_cols))
            win_y = yv[s : s + w]
            ys.append(int(win_y.any()))
            ff = famv[s : s + w][win_y == 1]
            fams.append(str(ff[0]) if len(ff) else "none")
            groups.append(ep)
    return np.array(xs), np.array(ys), np.array(fams), np.array(groups)
