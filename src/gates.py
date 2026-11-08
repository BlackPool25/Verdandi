"""Per-class structural gates (M0b fix): delay/loss/breakdown + Bernoulli CUSUM quality.

Pure functions on primitives. Precision-first operating points: each gate fires
only on a sustained, unambiguous signature; the OR-fusion in the battery runner
recovers recall across experts.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np

# 2x takt (takt=5): sustained release stall, not one missed cycle.
TPUTLAG_BAR = 10
# SHF DROPOUT boundary: exact-repeat run long enough to rule out coincidence.
STALE_BAR = 6
# Debounce: >=2 missed expected cycles before a stop event exists.
DOWN_BAR = 3


def delay_gate(tput_lag: int, state: str, *, bar: int = TPUTLAG_BAR) -> bool:
    """Throughput-lag gate: sustained release stall while the machine should produce.

    RUN-only: STARVED/IDLE machines legitimately sit at zero throughput all
    episode (clean STARVED machines saturate tputlag); DOWN is breakdown's
    jurisdiction. Gating on state, not just the counter, is the precision fix.
    """
    return tput_lag >= bar and state == "RUN"


def loss_gate(stale_count: int, *, bar: int = STALE_BAR) -> bool:
    """Stale-hold gate: sensor frozen long enough to rule out coincidence."""
    return stale_count >= bar


def loss_combo_gate(
    tput_lag: int, stale_count: int, *, tput_bar: int = 5, stale_bar: int = 1
) -> bool:
    """Loss signature that falls between the two bars: throughput stalled AND any
    exact-repeat present. Clean STARVED machines (tputlag saturated, stale == 0)
    never fire it; clean episodes measured stale max 0/10 eps."""
    return tput_lag >= tput_bar and stale_count >= stale_bar


def variance_exceeds(
    obs_1d: np.ndarray, baseline_var: float, *, window: int = 16, ratio: float = 4.0
) -> np.ndarray:
    """Quality gate: trailing-window variance vs clean baseline (precision-degradation
    signature). Point-wise ratio checks are noise; the window aggregates them."""
    x = np.asarray(obs_1d, dtype=float)
    if x.size < window or not np.isfinite(baseline_var) or baseline_var <= 0:
        return np.zeros(x.shape, dtype=bool)
    w = np.lib.stride_tricks.sliding_window_view(x, window)
    var = w.var(axis=1)
    out = np.zeros(x.shape, dtype=bool)
    out[window - 1 :] = var >= ratio * baseline_var
    return out


def breakdown_gate(down_run: int, *, bar: int = DOWN_BAR) -> bool:
    """DOWN-run gate: debounced stop event (natural or injected; attribution is walk's job)."""
    return down_run >= bar


def bernoulli_cusum_weights(p0: float, p1: float) -> tuple[float, float]:
    """Log-likelihood-ratio weights for pass/fail kit outcomes (p0 nominal, p1 design shift)."""
    if not (0 < p0 < p1 < 1):
        raise ValueError(f"need 0 < p0 < p1 < 1, got {p0}, {p1}")
    return math.log(p1 / p0), math.log((1 - p1) / (1 - p0))


def bernoulli_cusum_update(
    s: float, passed: bool, w_fail: float, w_pass: float, *, h: float
) -> tuple[float, bool]:
    """One Bernoulli-CUSUM step: reflect at 0, alarm at h."""
    s = max(0.0, s + (w_pass if passed else w_fail))
    return s, s >= h


def kit_outcomes_from_events(events: list[dict[str, Any]]) -> list[tuple[int, bool]]:
    """Per-kit (event-t, passed) in event order; a REJECT verdict consumes its paired REJECT_ROUTE (same part)."""
    out: list[tuple[int, bool]] = []
    pending_reject: set[Any] = set()
    for ev in events or []:
        typ = ev.get("event")
        detail = ev.get("detail") or {}
        t = int(ev.get("t", 0))
        if typ == "LATE_VERDICT":
            if detail.get("verdict") == "REJECT":
                pending_reject.add(detail.get("part"))
                out.append((t, False))
            else:
                pending_reject.discard(detail.get("part"))
                out.append((t, True))
        elif typ == "REJECT_ROUTE":
            if detail.get("part") in pending_reject:
                pending_reject.discard(detail.get("part"))
                continue
            out.append((t, False))
    return out


def track_counters(
    obs: np.ndarray,
    states: np.ndarray,
    throughput: np.ndarray,
    sigmas: list[float],
) -> dict[str, np.ndarray]:
    """Per-machine dwell/tputlag/downrun/stale counters (mirrors dataset_export semantics).

    All inputs machine-major [N, T]. stale uses exact-repeat within SHF_TOL*sigma.
    """
    from src import config as _config

    obs_a = np.asarray(obs, dtype=float)
    n, t_steps = obs_a.shape
    dwell = np.zeros((n, t_steps), dtype=int)
    tputlag = np.zeros((n, t_steps), dtype=int)
    downrun = np.zeros((n, t_steps), dtype=int)
    stale = np.zeros((n, t_steps), dtype=int)
    last_states: list[Any] = [None] * n
    last_obs: list[Any] = [None] * n
    for m in range(n):
        tol = max(1e-9, _config.SHF_TOL * float(sigmas[m]))
        for t in range(t_steps):
            st = states[m][t]
            dwell[m, t] = dwell[m, t - 1] + 1 if st == last_states[m] and t > 0 else 1
            last_states[m] = st
            downrun[m, t] = (
                downrun[m, t - 1] + 1
                if st == "DOWN" and t > 0
                else (1 if st == "DOWN" else 0)
            )
            tputlag[m, t] = (
                0 if throughput[m][t] > 0 else (tputlag[m, t - 1] + 1 if t > 0 else 1)
            )
            cur = float(obs_a[m, t])
            if last_obs[m] is not None and abs(cur - last_obs[m]) <= tol:
                stale[m, t] = stale[m, t - 1] + 1 if t > 0 else 1
            else:
                stale[m, t] = 0
                last_obs[m] = cur
    return {"dwell": dwell, "tputlag": tputlag, "downrun": downrun, "stale": stale}
