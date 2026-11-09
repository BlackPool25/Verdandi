"""Hybrid gate confirmer: structural counters confirm ML alarms.

Rule: obs families (bias/drift/quality/spike) pass ML decisions through
(their signatures live in obs channels, gates can't see them). Structural
families (delay/loss/breakdown) require a corroborating counter inside the
window — the gate that cannot hallucinate a stall the twin never ran.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

STRUCTURAL = {"delay", "loss", "breakdown"}
GATE_COL = {"delay": "cycle_lag", "loss": "stale_hold_run", "breakdown": "down_run"}
GATE_MIN = {"delay": 5, "loss": 1, "breakdown": 1}


def gate_support(
    df: pd.DataFrame, starts: np.ndarray, families: np.ndarray, *, w: int
) -> np.ndarray:
    """Per-window gate support: did the family's counter fire inside the window?

    Counters are step functions the twin physically ran — a positive run is
    corroboration, not another model's opinion.
    """
    st = np.asarray(starts, dtype=int)
    f = np.asarray(families, dtype=str)
    out = np.zeros(len(st), dtype=bool)
    for fam, col, bar in ((k, GATE_COL[k], GATE_MIN[k]) for k in sorted(STRUCTURAL)):
        if col not in df.columns:
            continue
        v = df[col].to_numpy()
        m = f == fam
        idx = np.flatnonzero(m)
        for i in idx:
            s = st[i]
            out[i] = bool((v[s : s + w] >= bar).any())
    return out


def apply_hybrid(
    dec: np.ndarray,
    fam: np.ndarray,
    gate_ok: np.ndarray,
) -> np.ndarray:
    """Keep ML decisions for obs families; require gate support for structural."""
    d = np.asarray(dec, dtype=int)
    f = np.asarray(fam, dtype=str)
    g = np.asarray(gate_ok, dtype=bool)
    out = d.copy()
    struct = np.isin(f, sorted(STRUCTURAL))
    out[struct] = (d[struct] & g[struct]).astype(int)
    return out
