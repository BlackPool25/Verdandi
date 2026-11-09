"""Diagnosis layer: attribution + sensor/process + rung/hop + onset (alongside detector).

Detector stays frozen (invariant HistGBM). This module only runs on
windows the detector fired on (silent on clean by construction).
Ground-truth columns (root_id_step, hop_step, sensor_vs_process,
mag_rung) are NEVER used here except in tests/evaluation.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

RUNG_CUT = 3.5


def episode_nominal(g: pd.DataFrame, obs_cols: list[str], n: int = 30) -> np.ndarray:
    """Per-channel nominal level from episode clean prefix (causal)."""
    return np.array(
        [g[c].to_numpy(dtype=float)[:n].mean() for c in obs_cols], dtype=float
    )


def robust_sigma(g: pd.DataFrame, obs_cols: list[str], n: int = 30) -> np.ndarray:
    """Per-channel MAD-based sigma from clean prefix (floor 1e-9)."""
    out = []
    for c in obs_cols:
        v = g[c].to_numpy(dtype=float)[:n]
        out.append(max(float(np.median(np.abs(v - np.median(v))) * 1.4826), 1e-9))
    return np.array(out, dtype=float)


def attribute_machine(
    seg: pd.DataFrame, obs_cols: list[str], nominal: np.ndarray, sigma: np.ndarray
) -> tuple[str, float]:
    """Argmax |last - nominal|/sigma over obs channels (alongside only)."""
    scores = {}
    last = seg.iloc[-1]
    for j, c in enumerate(obs_cols):
        scores[c] = abs(float(last[c]) - nominal[j]) / sigma[j]
    best = max(scores, key=lambda k: scores[k])
    machine = best.removeprefix("obs_")
    return machine, float(scores[best])


def classify_coordination(
    seg: pd.DataFrame,
    obs_cols: list[str],
    nominal: np.ndarray,
    sigma: np.ndarray,
    k: float = 3.0,
) -> str:
    """RBC-style: >=2 channels over kσ → process else sensor."""
    n_hit = 0
    last = seg.iloc[-1]
    for j, c in enumerate(obs_cols):
        if abs(float(last[c]) - nominal[j]) / sigma[j] > k:
            n_hit += 1
    return "process" if n_hit >= 2 else "sensor"


def estimate_rung(max_abs_sigma: float, cut: float = RUNG_CUT) -> str:
    """Severity readout: incipient (<cut) vs caricature (>=cut)."""
    return "caricature" if max_abs_sigma >= cut else "incipient"


def diagnose_window(
    seg: pd.DataFrame,
    obs_cols: list[str],
    nominal: np.ndarray,
    sigma: np.ndarray,
) -> dict:
    """Full per-window diagnosis dict (trigger-gated by caller)."""
    machine, score = attribute_machine(seg, obs_cols, nominal, sigma)
    coord = classify_coordination(seg, obs_cols, nominal, sigma)
    rung = estimate_rung(score)
    return {
        "machine": machine,
        "score_sigma": round(float(score), 3),
        "coord_class": coord,
        "rung": rung,
        "hop_est": 0,
    }
