"""State-feature tests (causal trailing windows, no future leakage)."""

from __future__ import annotations

import numpy as np
import pandas as pd


def _df() -> pd.DataFrame:
    n = 40
    obs = np.zeros((n, 2))
    obs[20:, 0] = np.linspace(0, 8, 20)  # ramp -> trailing variance grows after onset
    obs[20:, 1] = np.linspace(0, 4, 20)
    return pd.DataFrame(
        {
            "episode_id": [1] * n,
            "y": [0] * 20 + [1] * 20,
            "stale_hold_run": [0] * 18 + [1, 0] + [1, 0] * 10,
            "cycle_lag": list(range(n)),
            "reject_flag_count": [0] * 30 + [1] * 10,
            "buffer_occ": [5.0] * n,
            "obs_A0": obs[:, 0],
            "obs_A1": obs[:, 1],
        }
    )


def test_state_features_fire_after_onset_and_stay_causal():
    from scripts.train_tabular import add_state_features

    out = add_state_features(_df())
    for c in (
        "stale_rate_W",
        "tput_stall_W",
        "var_ratio_W",
        "slope_persist_W",
        "combo_loss",
    ):
        assert c in out.columns and np.isfinite(out[c].to_numpy()).all()
    # Causal: no signal before onset (rows 0..9 clean of the shift at 20,
    # but stale pattern exists; variance/slope must be ~0 early).
    assert float(out["var_ratio_W"].iloc[:10].max()) < float(
        out["var_ratio_W"].iloc[25:].max()
    )
    assert int(out["slope_persist_W"].iloc[5]) <= 5
    # combo_loss fires where cycle_lag>=5 and stale present.
    assert bool(out["combo_loss"].iloc[18]) is True
    assert bool(out["combo_loss"].iloc[0]) is False
