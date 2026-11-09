"""Hybrid gate confirmer tests (synthetic episodes)."""

from __future__ import annotations

import numpy as np
import pandas as pd


def test_gate_support_fires_on_counter_run_inside_window():
    from scripts.hybrid_gate import gate_support

    df = pd.DataFrame(
        {
            "cycle_lag": [0] * 20 + [7] * 10 + [0] * 34,
            "stale_hold_run": [0] * 64,
            "down_run": [0] * 64,
        }
    )
    fam = np.array(["delay"] * 4)
    starts = np.array([0, 8, 16, 24])
    g = gate_support(df, starts, fam, w=16)
    assert g.tolist() == [False, True, True, True]


def test_apply_hybrid_confirms_structural_passes_obs():
    from scripts.hybrid_gate import apply_hybrid

    dec = np.array([1, 1, 1, 1])
    fam = np.array(["delay", "loss", "spike", "bias"])
    gate = np.array([False, True, False, False])
    out = apply_hybrid(dec, fam, gate)
    assert out.tolist() == [0, 1, 1, 1]
