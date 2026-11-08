"""M0b baseline battery tests: aggregation helpers + 2-episode smoke (fast).

The full 192-episode audit runs via scripts/run_m0b_baseline.py (minutes, not suite-safe).
"""

from __future__ import annotations

import numpy as np
import pytest

from src import config, detect, train_pipeline, twin

pytestmark = [pytest.mark.k2, pytest.mark.k3, pytest.mark.battery]

MACHINES = list(config.MACHINE_NAMES)


def _aggregate(rows: list[dict]) -> dict:
    tp = sum(r["tp"] for r in rows)
    fp = sum(r["fp"] for r in rows)
    fn = sum(r["fn"] for r in rows)
    hits = [r for r in rows if r.get("fault_id")]
    y_true = np.array([1] * (tp + fn) + [0] * fp)
    y_pred = np.array([1] * tp + [0] * fn + [1] * fp)
    return {
        "f1": train_pipeline.compute_raw_pointwise_f1(y_true, y_pred),
        "ac1": sum(1 for r in hits if r["top"] == r["origin"]) / max(1, len(hits)),
        "n": len(rows),
    }


def test_aggregate_math():
    rows = [
        {"tp": 8, "fp": 2, "fn": 2, "fault_id": "F-1", "top": "A0", "origin": "A0"},
        {"tp": 0, "fp": 0, "fn": 10, "fault_id": "F-2", "top": "B1", "origin": "A1"},
    ]
    out = _aggregate(rows)
    assert out["ac1"] == pytest.approx(0.5)
    assert 0.0 < out["f1"] < 1.0


def test_two_episode_smoke_pins_score():
    import pathlib
    import sys

    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))
    import freeze_m0b_battery as fz
    import run_m0b_baseline as bl

    m = fz.build_manifest(master_seed=777)
    by_id = {r["id"]: (i, r) for i, r in enumerate(m["rows"])}
    thr = detect.fit_quantile_thresholds(twin.run_calibration(7), MACHINES)
    outs = []
    for fid in ("F-06", "F-21"):
        i, row = by_id[fid]
        rec = twin.run_episode(m["fault_episodes"][i], dict(row))
        outs.append(bl.score_episode(rec, dict(row), thr, MACHINES))
    assert all(o["hit"] for o in outs)
    assert outs[0]["latency"] <= 3
