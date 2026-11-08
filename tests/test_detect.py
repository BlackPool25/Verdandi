"""Phase-1 detector tests (PRISSUE-10): quantile/IQR artifact + VETO_ASM2 + miss drill."""

from __future__ import annotations

import numpy as np
import pytest

from src import config, detect, twin

pytestmark = [pytest.mark.k2, pytest.mark.k3, pytest.mark.battery]

MACHINES = list(config.MACHINE_NAMES)


def _cal_obs(seed: int = 7) -> np.ndarray:
    return twin.run_calibration(seed)


def test_fit_thresholds_max_rule_all_machines():
    thr = detect.fit_quantile_thresholds(_cal_obs(), MACHINES)
    assert set(thr) == set(MACHINES)
    for t in thr.values():
        assert t["thr"] >= t["q99"] and t["thr"] >= t["fence"]
        assert t["n"] == config.CAL_WIN - config.WARMUP_STEPS


def test_fit_deterministic_same_seed():
    a = detect.fit_quantile_thresholds(_cal_obs(7), MACHINES)
    b = detect.fit_quantile_thresholds(_cal_obs(7), MACHINES)
    assert a == b


def test_clean_mask_excludes_fault_steps():
    rng = np.random.default_rng(0)
    x = rng.normal(size=(300, 1))
    x[50:60, 0] += 6.0
    masked = detect.fit_quantile_thresholds(x, ["A0"], clean_mask=np.arange(300) < 50)
    unmasked = detect.fit_quantile_thresholds(x, ["A0"])
    assert masked["A0"]["thr"] < unmasked["A0"]["thr"]


def test_artifact_round_trip_pins_version(tmp_path):
    thr = detect.fit_quantile_thresholds(_cal_obs(), MACHINES)
    p = tmp_path / "quantile.json"
    detect.save_artifact(p, thr, cal_seed=7)
    back = detect.load_artifact(p)
    assert back["thresholds"] == thr
    assert back["code_version"] == config.CODE_VERSION


def test_artifact_rejects_wrong_version(tmp_path):
    import json

    p = tmp_path / "bad.json"
    p.write_text(json.dumps({"version": "nope", "thresholds": {}}))
    with pytest.raises(ValueError, match="version"):
        detect.load_artifact(p)


def test_exceedance_fires_at_spike_only():
    thr = {m: {"thr": 3.0} for m in MACHINES}
    obs = np.zeros((10, len(MACHINES)))
    obs[4, MACHINES.index("B2")] = 5.0
    alarms, scores = detect.detect_exceedance(obs, thr, MACHINES)
    assert alarms.sum() == 1 and alarms[4, MACHINES.index("B2")]
    assert scores[4, MACHINES.index("B2")] == pytest.approx(2.0)


def test_veto_asm2_requires_double_margin():
    peaks = {"ASM2": 1.5, "A2": 1.0, "B2": 0.2}
    assert detect.apply_veto_asm2(peaks) == "A2"
    peaks = {"ASM2": 3.0, "A2": 1.0, "B2": 0.2}
    assert detect.apply_veto_asm2(peaks) == "ASM2"


def test_miss_drill_oracle_pins_detected():
    import pathlib
    import sys

    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))
    import freeze_m0b_battery as fz

    m = fz.build_manifest(master_seed=777)
    by_id = {r["id"]: (i, r) for i, r in enumerate(m["rows"])}
    thr = detect.fit_quantile_thresholds(_cal_obs(), MACHINES)

    def drill(fid):
        i, row = by_id[fid]
        rec = twin.run_episode(m["fault_episodes"][i], dict(row))
        obs = np.asarray(rec["obs"], dtype=float).T
        alarms, scores = detect.detect_exceedance(obs, thr, MACHINES)
        top, lat = detect.attribute_top1(
            scores, int(row["t0"]), int(row["dur"]), MACHINES
        )
        rec_hit = bool(
            alarms[
                int(row["t0"]) : int(row["t0"]) + int(row["dur"]) + 3,
                MACHINES.index(row["origin"]),
            ].any()
        )
        return top, lat, rec_hit, row["origin"]

    top, lat, hit, origin = drill("F-06")
    assert hit and top == origin and lat <= 3
    # F-21 drift ramps: must flag the origin (late flag = DELAY taxonomy, not a miss)
    top, lat, hit, origin = drill("F-21")
    assert hit and top == origin
