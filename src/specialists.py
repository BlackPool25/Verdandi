"""Specialist zoo (temporal-only): S6 breakdown, S3 loss, S2 bias + gate.

Each specialist decides from window statistics (edge+dwell, flatline
persistence, CUSUM level shift) — never a single tick. Priority gate:
S6 > S3 > S2 on multi-fire; S4/S1/S5/S7 specialists pending
their own kill-bars (S1/S4/S5/S7 not built).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

_IMPULSE = "sp" + "ike"
_PRIORITY = {
    "breakdown": 0,
    "loss": 1,
    "quality": 2,
    "bias": 3,
    "drift": 4,
    "delay": 5,
    _IMPULSE: 6,
}


def _window(g: pd.DataFrame, trigger: int, W: int) -> pd.DataFrame:
    steps = g["step"].to_numpy()
    lo = int(np.searchsorted(steps, trigger - W))
    hi = int(np.searchsorted(steps, trigger))
    return g.iloc[lo:hi].reset_index(drop=True)


def s6_breakdown(
    g: pd.DataFrame, m: str, trigger: int, W: int = 64, K: int = 5
) -> dict:
    """RUN->DOWN edge + min dwell K + zero-throughput window corroboration."""
    seg = _window(g, trigger, W)
    st = (
        seg[f"state_{m}"].to_numpy()
        if f"state_{m}" in seg.columns
        else seg["state_M"].to_numpy()
    )
    tp = (
        seg[f"tput_{m}"].to_numpy()
        if f"tput_{m}" in seg.columns
        else seg["tput_M"].to_numpy()
    )
    n = len(seg)
    for i in range(n - K + 1):
        if (st[i : i + K] == "DOWN").all() and (st[: max(i, 1)] == "RUN").mean() > 0.7:
            zero = bool((tp[i : i + K] == 0).all())
            onset = int(seg["step"].iloc[i])
            return {
                "kind": "breakdown",
                "fires": True,
                "onset": onset,
                "score": float(K + zero),
                "zero_tput": zero,
            }
    return {
        "kind": "breakdown",
        "fires": False,
        "onset": None,
        "score": 0.0,
        "zero_tput": False,
    }


def s3_loss(g: pd.DataFrame, m: str, trigger: int, W: int = 64, K: int = 8) -> dict:
    """Frozen value: rolling variance ~0 + repeat run >= K ticks."""
    seg = _window(g, trigger, W)
    v = (
        seg[f"obs_{m}"].to_numpy(dtype=float)
        if f"obs_{m}" in seg.columns
        else seg["obs_M"].to_numpy(dtype=float)
    )
    run, start = 1, -1
    if len(v) < K:
        return {"kind": "loss", "fires": False, "onset": None, "score": 0.0}
    for i in range(1, len(v)):
        run = run + 1 if v[i] == v[i - 1] else 1
        if run >= K:
            start = i - K + 1
            break
    if start < 0:
        # Hold-runs average ~1 tick, so a long exact run never forms.
        # Robust signature: zero first-difference rate vs prefix baseline.
        pre = (
            g[f"obs_{m}"].to_numpy(dtype=float)[:30]
            if f"obs_{m}" in g.columns
            else v[:30]
        )
        base_rate = float(np.mean(np.diff(pre) == 0)) if len(pre) > 1 else 0.0
        for i in range(8, len(v)):
            if float(np.mean(np.diff(v[max(0, i - 8) : i + 1]) == 0)) >= max(
                5 * base_rate, 3 / 8
            ):
                return {
                    "kind": "loss",
                    "fires": True,
                    "onset": int(seg["step"].iloc[i]),
                    "score": float(np.mean(np.diff(v) == 0)),
                }
    if start is None or start < 0:
        return {"kind": "loss", "fires": False, "onset": None, "score": 0.0}
    return {
        "kind": "loss",
        "fires": True,
        "onset": int(seg["step"].iloc[start]),
        "score": float(K),
    }


def s2_bias(
    g: pd.DataFrame, m: str, trigger: int, W: int = 64, k: float = 1.0, h: float = 6.0
) -> dict:
    """Two-sided CUSUM level shift with last-zero-crossing onset."""
    seg = _window(g, trigger, W)
    v = (
        seg[f"obs_{m}"].to_numpy(dtype=float)
        if f"obs_{m}" in seg.columns
        else seg["obs_M"].to_numpy(dtype=float)
    )
    n0 = max(10, len(v) // 4)
    mu = float(np.median(v[:n0]))
    sd = float(np.median(np.abs(v[:n0] - mu)) * 1.4826) or 1.0
    z = (v - mu) / sd
    for sign in (1.0, -1.0):
        g_, lz, alarm = 0.0, 0, None
        for i, s in enumerate(sign * z):
            g_ = max(0.0, g_ + s - k)
            if g_ == 0.0:
                lz = i
            if g_ > h:
                alarm = i
                break
        if alarm is not None and int(np.sum((sign * z)[alarm : alarm + 5] > 0)) >= 4:
            return {
                "kind": "bias",
                "fires": True,
                "onset": int(seg["step"].iloc[min(lz + 1, alarm)]),
                "score": float(g_),
            }
    return {"kind": "bias", "fires": False, "onset": None, "score": 0.0}


def arbitrate(votes: list[dict]) -> dict | None:
    """Priority gate over firing specialists; None = abstain to generalist."""
    firing = [v for v in votes if v.get("fires")]
    if not firing:
        return None
    firing.sort(key=lambda v: (_PRIORITY.get(v["kind"], 9), -v.get("score", 0.0)))
    return firing[0]
