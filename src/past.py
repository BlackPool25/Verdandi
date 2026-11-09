"""PAST capture: trajectory-only change cards (no snapshots).

Per machine, per frozen trigger T: PAST=[T-W,T) split into BASE/RECENT;
state-trajectory deltas, counter-trajectory slopes, CUSUM/BOCPD-style
onset tau with persistence hold. Single-tick values are never rankers.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

_STATES = ("RUN", "STARVED", "BLOCKED", "DOWN")


def _hist(row: np.ndarray) -> np.ndarray:
    p = np.array([np.mean(row == s) for s in _STATES], dtype=float)
    return p / max(p.sum(), 1e-9)


def _js(p: np.ndarray, q: np.ndarray) -> float:
    m = 0.5 * (p + q)
    out = 0.0
    for a in (p, q):
        nz = a > 0
        out += float(np.sum(a[nz] * np.log(a[nz] / np.maximum(m[nz], 1e-12))))
    return float(0.5 * out)


def _cusum_tau(
    v: np.ndarray, k: float = 1.0, h: float = 6.0, hold: int = 5
) -> int | None:
    """Onset = last zero-crossing before first threshold crossing (Page).

    Requires the post-crossing mass to stay positive `hold` ticks
    (fleeting texture does not confirm).
    """
    x = np.asarray(v, dtype=float)
    n0 = max(10, len(x) // 4)
    mu = float(np.median(x[:n0]))
    sd = float(np.median(np.abs(x[:n0] - mu)) * 1.4826) or 1.0
    z = (x - mu) / sd
    g, last_zero, alarm = 0.0, 0, None
    for i, s in enumerate(z):
        g = max(0.0, g + s - k)
        if g == 0.0:
            last_zero = i
        if g > h:
            alarm = i
            break
    if alarm is None:
        return None
    run = int(np.sum(z[alarm : alarm + hold] > 0))
    if run < hold - 1:
        return None
    return int(min(last_zero + 1, alarm))


def _slope(v: np.ndarray) -> float:
    x = np.asarray(v, dtype=float)
    if len(x) < 3:
        return 0.0
    t = np.arange(len(x), dtype=float)
    t -= t.mean()
    return float((t * (x - x.mean())).sum() / max((t * t).sum(), 1e-9))


def build_past_card(g: pd.DataFrame, machine: str, trigger: int, W: int = 64) -> dict:
    """Trajectory-only change card for one machine at a trigger tick."""
    steps = g["step"].to_numpy()
    lo = int(np.searchsorted(steps, trigger - W))
    hi = int(np.searchsorted(steps, trigger))
    seg = g.iloc[lo:hi].reset_index(drop=True)
    n = len(seg)
    half = n // 2
    obs_c, state_c = f"obs_{machine}", f"state_{machine}"
    out: dict = {"machine": machine, "trigger": trigger, "W": W, "n": n}

    st = seg[state_c].to_numpy() if state_c in seg.columns else np.array(["RUN"] * n)
    out["state_delta"] = _js(_hist(st[:half]), _hist(st[half:]))
    out["dwell_collapse"] = float(
        np.mean(st[:half] == "RUN") - np.mean(st[half:] == "RUN")
    )

    slopes = {}
    for cc in (f"tputlag_{machine}", f"downrun_{machine}", f"dwell_{machine}"):
        if cc in seg.columns:
            v = seg[cc].to_numpy(dtype=float)
            slopes[cc] = {
                "slope": _slope(v),
                "post_max": float(v[half:].max(initial=0.0)),
            }
    out["counter_slopes"] = slopes

    v = seg[obs_c].to_numpy(dtype=float) if obs_c in seg.columns else np.zeros(n)
    pre = g[obs_c].to_numpy(dtype=float)[:30] if obs_c in g.columns else np.zeros(30)
    med = float(np.median(pre))
    mad = float(np.median(np.abs(pre - med)) * 1.4826) or 1.0
    tau = _cusum_tau((v - med) / mad)
    # state-edge tau overrides: sustained RUN->non-RUN run anywhere in PAST
    # whose prefix is clean-RUN dominated (else plant transient).
    for i in range(n - 2):
        if (st[i : i + 3] != "RUN").all() and (st[: max(i, 1)] == "RUN").mean() > 0.7:
            tau = i if tau is None else min(tau, i)
            break
    out["tau"] = int(steps[lo + tau]) if tau is not None else None
    out["persistent"] = tau is not None
    return out
