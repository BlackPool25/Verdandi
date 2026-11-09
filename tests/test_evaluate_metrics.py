"""Metric-harness smoke test (synthetic battery, no twin)."""

from __future__ import annotations

import json

import numpy as np
import pandas as pd


def test_evaluate_metrics_runs_on_synthetic_battery(tmp_path):
    n = 64
    df = pd.DataFrame(
        {
            "episode_id": [1] * n + [2] * n,
            "step": list(range(n)) * 2,
            "y": [0] * 32 + [1] * 32 + [0] * n,
            "fault_family": ["none"] * 32 + ["spike"] * 32 + ["none"] * n,
            **{f"obs_A{i}": np.zeros(n * 2) for i in range(3)},
            "cycle_lag": [0] * (2 * n),
            "stale_hold_run": [0] * (2 * n),
            "reject_flag_count": [0] * (2 * n),
            "degrade_flag_count": [0] * (2 * n),
        }
    )
    pq = tmp_path / "s.parquet"
    df.to_parquet(pq)
    man = {
        "fault_episodes": [1],
        "clean_episodes": [2],
        "rows": [
            {
                "class": "spike",
                "t0": 32,
                "dur": 32,
                "origin": "A0",
                "id": "T1",
                "mag_rung": "caricature",
                "mag_sigma": 5.0,
                "rep": False,
                "sev": 5.0,
            }
        ],
    }
    mp = tmp_path / "m.json"
    mp.write_text(json.dumps(man))
    from sklearn.model_selection import StratifiedGroupKFold

    from scripts.train_windows import train_binary_gbm
    from src.window_dataset import apply_norm, build_windows, fit_clean_norm

    X, y, fam, groups = build_windows(df, w=16, stride=16, invariant=True)
    oof = np.zeros(len(X))
    cv = StratifiedGroupKFold(n_splits=2)
    for tr, te in cv.split(X, y, groups):
        med, iqr = fit_clean_norm(X[tr], y[tr], X.shape[1] - 8)
        clf = train_binary_gbm(apply_norm(X[tr], med, iqr, X.shape[1] - 8), y[tr])
        oof[te] = clf.predict_proba(apply_norm(X[te], med, iqr, X.shape[1] - 8))[:, 1]
    op = tmp_path / "oof.parquet"
    pd.DataFrame(
        {
            "score": oof,
            "dec": (oof >= 0.5).astype(int),
            "y": y,
            "fam": fam,
            "ep": groups,
        }
    ).to_parquet(op)
    from scripts.evaluate_metrics import main

    assert (
        main(
            [
                "--oof",
                str(op),
                "--parquet",
                str(pq),
                "--manifest",
                str(mp),
                "--w",
                "16",
                "--stride",
                "16",
            ]
        )
        == 0
    )
