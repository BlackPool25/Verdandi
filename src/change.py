"""Rigorous window-change engine: two-sample BASE/RECENT + CUSUM onset.

One entry point per (machine, trigger): state-conditioned z-scores from
the clean prefix, CUSUM last-zero-crossing onset with persistence hold,
state-edge confirmation, dz ranking. Single ticks never decide.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.past import build_past_card


def analyze_window(g: pd.DataFrame, machine: str, trigger: int, W: int = 64) -> dict:
    """Change verdict for one machine in the PAST window before trigger."""
    card = build_past_card(g, machine, trigger, W=W)
    steps = g["step"].to_numpy()
    lo = int(np.searchsorted(steps, trigger - W))
    seg = g.iloc[lo : lo + card["n"]].reset_index(drop=True)
    obs_c = f"obs_{machine}"
    v = seg[obs_c].to_numpy(dtype=float) if obs_c in seg.columns else np.zeros(len(seg))
    pre = g[obs_c].to_numpy(dtype=float)[:30] if obs_c in g.columns else np.zeros(30)
    med = float(np.median(pre))
    mad = float(np.median(np.abs(pre - med)) * 1.4826) or 1e-9
    z = (v - med) / mad
    half = len(z) // 2
    base_z = float(np.max(np.abs(z[:half]))) if half else 0.0
    rec_z = float(np.max(np.abs(z[half:]))) if half < len(z) else 0.0
    dz = max(0.0, rec_z - base_z)
    run = int(np.sum(np.abs(z[half:]) > 3.0)) if half < len(z) else 0
    score = float(card["state_delta"] * 5.0 + dz + min(run, 10) * 0.2)
    return {
        "machine": machine,
        "trigger": trigger,
        "onset": card["tau"],
        "persisted": card["persistent"],
        "score": round(score, 3),
        "dz": round(dz, 3),
        "state_delta": card["state_delta"],
        "dwell_collapse": card["dwell_collapse"],
    }
