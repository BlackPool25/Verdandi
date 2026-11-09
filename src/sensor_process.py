"""D2 combine (machine-agnostic): shape veto -> quality-lift -> WIP/balance
-> coordination count. No per-machine identity needed; stages are ordered
and any stage below its kill-bar is removed, not tuned around.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def _col(g: pd.DataFrame, name: str, default: float = 0.0) -> np.ndarray:
    if name in g.columns:
        return g[name].to_numpy(dtype=float)
    return np.full(len(g), default)


def shape_veto(g: pd.DataFrame, m: str, start: int = 100) -> str | None:
    """Stuck/flatline sensor signature -> 'sensor', else None."""
    v = _col(g, f"obs_{m}", 0.0)
    if len(v) <= start + 8:
        return None
    base = float(np.mean(np.diff(v[:start]) == 0)) if start > 1 else 0.0
    win = v[start:]
    for i in range(8, len(win)):
        seg = win[max(0, i - 8) : i + 1]
        if float(np.mean(np.diff(seg) == 0)) >= max(5 * base, 0.25):
            return "sensor"
    return None


def quality_lift(g: pd.DataFrame, trigger: int | None = None) -> bool:
    """Reject/degrade surge after trigger -> process (quality faults move parts)."""
    n = len(g)
    steps = g["step"].to_numpy() if "step" in g.columns else np.arange(n)
    t = n // 2 if trigger is None else int(trigger)
    mid = max(1, int(np.searchsorted(steps, t)))
    post = float(
        _col(g, "reject_flag_count")[mid:].sum()
        + _col(g, "degrade_flag_count")[mid:].sum()
    )
    pre_n = float(
        _col(g, "reject_flag_count")[:mid].sum()
        + _col(g, "degrade_flag_count")[:mid].sum()
    )
    return bool(post >= 3 and post > 2 * pre_n)


def wip_moved(g: pd.DataFrame, trigger: int, k: float = 5.0, hold: int = 5) -> bool:
    """Sustained buffer-occupancy excursion after trigger -> process."""
    v = _col(g, "buffer_occ")
    steps = g["step"].to_numpy() if "step" in g.columns else np.arange(len(g))
    i0 = int(np.searchsorted(steps, trigger))
    pre = v[: max(10, i0)]
    med = float(np.median(pre))
    mad = float(np.median(np.abs(pre - med)) * 1.4826) or 1e-9
    run = 0
    for x in v[i0:]:
        run = run + 1 if abs(x - med) > k * mad else 0
        if run >= hold:
            return True
    return False


def _structural(g: pd.DataFrame, m: str, i0: int, hold: int = 3) -> bool:
    """DOWN, BLOCKED-with-hold, or counter exceeding its prefix max."""
    scol = f"state_{m}"
    if scol in g.columns:
        w = g[scol].to_numpy()[i0 : i0 + 20]
        if len(w) >= hold and (
            (w == "DOWN").sum() >= hold or (w == "BLOCKED").sum() >= hold
        ):
            return True
    for cc in (f"tputlag_{m}", f"downrun_{m}"):
        if cc in g.columns:
            v = g[cc].to_numpy(dtype=float)
            pm = float(v[: max(10, i0)].max(initial=0.0))
            if bool((v[i0 : i0 + 20] > pm).sum() >= hold):
                return True
    return False


def coordination(
    g: pd.DataFrame, machines: list[str], trigger: int, W: int = 64
) -> str:
    """Changed machines split by state: structural involvement -> process
    vote; clean-RUN residual-only -> sensor vote. STARVED-only victims
    don't vote (downstream symptoms). Process wins ties (fault present).
    """
    steps = g["step"].to_numpy() if "step" in g.columns else np.arange(len(g))
    i0 = int(np.searchsorted(steps, trigger))
    seg = g.iloc[i0 : i0 + W]
    proc_votes, sens_votes = 0, 0
    for m in machines:
        c = f"obs_{m}"
        if c not in g.columns:
            continue
        v = seg[c].to_numpy(dtype=float) if len(seg) else np.array([])
        pv = g[c].to_numpy(dtype=float)[:30]
        med = float(np.median(pv))
        mad = float(np.median(np.abs(pv - med)) * 1.4826) or 1e-9
        z = np.abs((v - med) / mad)
        run = 0
        for s in z:
            run = run + 1 if s > 2.5 else 0
            if run >= 5:
                break
        if run < 5:
            continue
        scol = f"state_{m}"
        own = str(seg[scol].iloc[0]) if scol in seg.columns and len(seg) else "RUN"
        if own == "STARVED":
            continue  # downstream symptom: no vote
        if _structural(g, m, i0):
            proc_votes += 1
        elif own == "RUN":
            sens_votes += 1
        else:
            proc_votes += 1
    if proc_votes == 0 and sens_votes == 0:
        return "abstain"
    return "process" if proc_votes > 0 else "sensor"


def decide(g: pd.DataFrame, machines: list[str], trigger: int) -> dict:
    """Staged combine. Returns {verdict, stage}."""
    for m in machines:
        if f"obs_{m}" in g.columns and shape_veto(g, m) == "sensor":
            return {"verdict": "sensor", "stage": "shape"}
    if quality_lift(g, trigger):
        return {"verdict": "process", "stage": "quality"}
    if wip_moved(g, trigger):
        return {"verdict": "process", "stage": "wip"}
    c = coordination(g, machines, trigger)
    if c == "abstain":
        return {"verdict": "abstain", "stage": "coordination"}
    return {"verdict": c, "stage": "coordination"}
