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

# STRUCT_COLS 2026-11-09: stale_hold_run + reject_flag_count BANNED from
# the identity path — proven GT-anchored in this battery (clean rows
# exactly constant: stale_hold_run 108151/108151 zeros, reject_flag_count
# single value; v6 root-anchored branch with zero fallback). cycle_lag +
# degrade_flag_count kept: clean rows vary (19/5 uniques), v5-style
# causal max/median computation, computable at serve time.
# FROZEN EXCEPTION: the invariant path (v7 detector, 23-feat quarantine)
# keeps all four until the stale/reject-importance ablation in v7 lands.
STRUCT_COLS: tuple = ("cycle_lag", "stale_hold_run", "reject_flag_count", "degrade_flag_count")
OBS_STRUCT_COLS: tuple = ("cycle_lag", "degrade_flag_count")


def struct_cols_for(*, invariant: bool) -> tuple:
    """Struct cols per path: frozen four for invariant, clean two otherwise."""
    return STRUCT_COLS if invariant else OBS_STRUCT_COLS

# Proven GT-anchored in m0b-mass battery (clean rows exactly constant,
# v6 root-anchored branch with zero fallback): stale_hold_run, down_run,
# reject_flag_count — plus label columns by prefix. dwell_steps,
# cycle_lag, state_hist_delta, degrade_flag_count, buffer_occ vary on
# clean rows (v5-style causal computation) and stay allowed.
GT_ANCHORED_COLS = (
    "stale_hold_run", "down_run", "reject_flag_count",
)


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


def _window_features(
    seg: pd.DataFrame, obs_cols: list[str], struct_cols: tuple = OBS_STRUCT_COLS
) -> np.ndarray:
    parts = []
    for c in obs_cols:
        v = seg[c].to_numpy(dtype=float)
        parts += [v.mean(), v.std(), v.min(), v.max(), v[-1] - v[0]]
    for c in struct_cols:
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
    # Frozen: invariant detector (v7, 23 feats) keeps all four struct cols.
    struct = _window_features(seg, [], STRUCT_COLS)[-8:]
    return np.concatenate([out, struct])


def _episode_windows(job: tuple) -> tuple:
    """One episode's windows. Module-level so worker processes can pickle it."""
    (g, obs_cols, ep, off, w, stride, invariant) = job
    g = g.sort_values("step").reset_index(drop=True)
    yv = g["y"].to_numpy(dtype=int)
    famv = (
        g["fault_family"].to_numpy()
        if "fault_family" in g
        else np.array(["none"] * len(g))
    )
    xs, ys, fams, groups, starts, roots = [], [], [], [], [], []
    has_root = "root_id_step" in g.columns
    rootv = g["root_id_step"].to_numpy() if has_root else np.array([""] * len(g))
    for s in range(off, len(g) - w + 1, stride):
        seg = g.iloc[s : s + w]
        base = (
            _window_features_invariant(seg, obs_cols)
            if invariant
            else _window_features(seg, obs_cols)
        )
        xs.append(base)
        win_y = yv[s : s + w]
        ys.append(int(win_y.any()))
        ff = famv[s : s + w][win_y == 1]
        fams.append(str(ff[0]) if len(ff) else "none")
        groups.append(ep)
        starts.append(s)
        rr = rootv[s : s + w][win_y == 1]
        if len(rr):
            vals, counts = np.unique(rr.astype(str), return_counts=True)
            roots.append(str(vals[int(np.argmax(counts))]))
        else:
            roots.append("none")
    return (xs, ys, fams, groups, starts, roots)


def build_windows(
    df: pd.DataFrame,
    *,
    w: int = 32,
    stride: int = 8,
    invariant: bool = False,
    offset: int = 0,
    jitter: int = 0,
    seed: int = 0,
    return_starts: bool = False,
    return_roots: bool = False,
    build_jobs: int = 1,
) -> tuple:
    """Slide windows over each episode; return (X, y, fam, groups).

    invariant=True emits origin-invariant features (no channel identity).
    offset shifts the grid phase (streaming inference never aligns to the
    training grid; offset=stride//2 is the worst case to test).
    jitter>0 draws a per-episode grid offset in [0, jitter) (phase-jittered
    training: free shift augmentation, no new data).
    return_starts=True appends window start ticks (needed for point
    aggregation) as a fifth element. return_roots=True appends the
    per-window root machine (mode of root_id_step over fault steps,
    "none" when clean) as the last element.
    build_jobs>1 fans episodes out to worker processes (order-preserving;
    jitter draws stay serial so the grid is identical to build_jobs=1).
    """
    if w < 1:
        raise ValueError(f"w must be >= 1, got {w}")
    if stride < 1:
        raise ValueError(f"stride must be >= 1, got {stride}")
    obs_cols = [c for c in df.columns if c.startswith("obs_")]
    rng = np.random.default_rng(seed)
    jobs = []
    for ep, g in df.groupby("episode_id", sort=False):
        off = offset + (int(rng.integers(0, max(1, jitter))) if jitter else 0)
        jobs.append((g, obs_cols, ep, off, w, stride, invariant))
    if build_jobs == 1:
        parts = [_episode_windows(j) for j in jobs]
    else:
        from concurrent.futures import ProcessPoolExecutor

        with ProcessPoolExecutor(max_workers=build_jobs) as ex:
            parts = list(ex.map(_episode_windows, jobs))
    xs, ys, fams, groups, starts, roots = [], [], [], [], [], []
    for px, py, pf, pg, ps, pr in parts:
        xs += px
        ys += py
        fams += pf
        groups += pg
        starts += ps
        roots += pr
    X, y, fam, grp = (np.array(xs), np.array(ys), np.array(fams), np.array(groups))
    out: tuple = (X, y, fam, grp)
    if return_starts:
        out += (np.array(starts),)
    if return_roots:
        out += (np.array(roots),)
    return out


def aggregate_to_points(
    scores: np.ndarray,
    groups: np.ndarray,
    starts: np.ndarray,
    *,
    w: int,
    n_steps: int | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Darts-pattern dense inference: point score = mean over covering windows.

    Returns (point_scores, point_episode, point_step): one row per tick covered
    by at least one window. A tick covered by k windows averages k scores, so
    detections localize to ticks instead of 128-wide blocks and grid phase
    washes out with dense stride.
    """
    s = np.asarray(scores, dtype=float)
    g = np.asarray(groups)
    st = np.asarray(starts, dtype=int)
    out_s, out_g, out_t = [], [], []
    for ep in np.unique(g):
        m = g == ep
        se, ss = st[m], s[m]
        t_max = int((se + w).max()) if len(se) else 0
        if n_steps is not None:
            t_max = min(t_max, int(n_steps))
        for t in range(t_max):
            cov = ss[(se <= t) & (t < se + w)]
            if len(cov):
                out_s.append(float(cov.mean()))
                out_g.append(ep)
                out_t.append(t)
    return np.array(out_s), np.array(out_g), np.array(out_t)
