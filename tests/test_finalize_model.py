"""Final model artifact tests (train -> save -> reload identical)."""

from __future__ import annotations

import json

import joblib
import numpy as np
import pandas as pd


def _tiny_df() -> pd.DataFrame:
    n = 96
    return pd.DataFrame(
        {
            "episode_id": [1] * n + [2] * n + [3] * n,
            "step": list(range(n)) * 3,
            "y": [0] * 48 + [1] * 48 + [0] * 48 + [1] * 48 + [0] * 48 + [1] * 48,
            "fault_family": ["none"] * 48
            + ["delay"] * 48
            + ["none"] * 48
            + ["loss"] * 48
            + ["none"] * 48
            + ["spike"] * 48,
            "obs_A0": np.concatenate(
                [np.zeros(48), np.linspace(0, 8, 48)] * 2 + [np.zeros(96)]
            ),
            "cycle_lag": list(range(n)) * 3,
            "stale_hold_run": [0] * (n * 3),
            "reject_flag_count": [0] * (n * 3),
            "degrade_flag_count": [0] * (n * 3),
        }
    )


def test_finalize_trains_calibrates_saves_and_reloads(tmp_path):
    from scripts.finalize_window_model import finalize

    out = tmp_path / "vtest"
    r = finalize(_tiny_df(), out_dir=str(out), w=16, stride=16, seed=0)
    assert (out / "model.joblib").exists()
    assert (out / "thresholds.json").exists()
    assert (out / "schema.json").exists()
    assert r["window_f1"] > 0.5
    art0 = joblib.load(out / "model.joblib")
    assert {"norm_median", "norm_iqr", "n_obs_features"} <= set(art0)
    schema = json.loads((out / "schema.json").read_text())
    assert schema["w"] == 16 and len(schema["features"]) == r["n_features"]
    # Reload: identical predictions.
    art = joblib.load(out / "model.joblib")
    from src.window_dataset import build_windows

    X, _, _, _ = build_windows(_tiny_df(), w=16, stride=16)
    p1 = art["model"].predict_proba(X)[:, 1]
    art2 = joblib.load(out / "model.joblib")
    p2 = art2["model"].predict_proba(X)[:, 1]
    assert np.array_equal(p1, p2)
