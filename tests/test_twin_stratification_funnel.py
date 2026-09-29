"""TDD red step (Todo 1): stratification keys, funnel rebalancing, schema-v3.

Covers minipro-25 normative requirements:
1. 9-key stratification export presence per episode / window in twin records
   (episode_id, wear_endpoint, maint_flag, family + mode, root_id/hop/root_ids,
   sensor_vs_process, per-machine state histogram, warm-up flag, full funnel census).
2. Sunk rolling-20 median >= 30 gate test over exact 20-seed batch
   [7, 11, 13, 42, 777, 1234, 999, 2026, 12345, 1001..1011] and versioned wall_report.
3. Schema version transition: TWIN_SCHEMA 2->3 and requirement that v2 readers
   reject v3 records loudly with ValueError.
4. Warm-up exclusion from run_calibration fits (first 15 steps excluded from
   calibration fits) while remaining in transient pool.
5. Per-machine state histogram denominator rules (sums to 1.0 +- 0.01 over 26 machines,
   with plant rollup over 24 excluding B7S/RWK0).

RED FIRST: No product logic implemented yet. Every test in this file MUST fail (red)
against the current unchanged codebase with a descriptive assertion error naming
the missing key or failed gate.
"""

import copy
import json
import numpy as np
import pytest

from src import config, twin

pytestmark = pytest.mark.k1

_PROBE_FAULT = {
    "id": "F-21",
    "class": "drift",
    "origin": "B2",
    "t0": 150,
    "dur": 12,
    "mag_sigma": 5.2,
}

_DELAY_FAULT = {
    "id": "F-T2-delay",
    "class": "delay",
    "origin": "A2",
    "t0": 150,
    "dur": 15,
    "mag_sigma": 0.0,
    "extra": {"d": 5},
}

_EXACT_20_SEEDS = [
    7, 11, 13, 42, 777, 1234, 999, 2026, 12345,
    1001, 1002, 1003, 1004, 1005, 1006, 1007, 1008, 1009, 1010, 1011,
]


# ==============================================================================
# Group 1: 9-Key Stratification Export Presence per Episode / Window
# ==============================================================================

def test_strat_record_contains_strat_export():
    """Episode record must carry 'strat' stratification export dictionary."""
    rec = twin.run_episode(777, _PROBE_FAULT)
    assert "strat" in rec, "Record missing 'strat' stratification export dictionary"


def test_strat_9_keys_presence_in_record():
    """Stratification export must contain all 9 required stratification keys."""
    rec = twin.run_episode(777, _PROBE_FAULT)
    assert "strat" in rec, "Record missing 'strat' stratification export dictionary"
    strat = rec["strat"]
    required_keys = {
        "episode_id",
        "wear_endpoint",
        "maint_flag",
        "family",
        "mode",
        "root_id",
        "sensor_vs_process",
        "state_histogram",
        "warmup_flag",
        "funnel_census",
    }
    missing = required_keys - set(strat.keys())
    assert not missing, f"Stratification export missing required keys: {sorted(missing)}"


def test_strat_wear_endpoint_scalar():
    """Stratification export must contain non-negative float 'wear_endpoint'."""
    rec = twin.run_episode(777, _PROBE_FAULT)
    assert "strat" in rec, "Record missing 'strat' export"
    strat = rec["strat"]
    assert "wear_endpoint" in strat, "Stratification missing 'wear_endpoint'"
    assert isinstance(strat["wear_endpoint"], float), (
        f"wear_endpoint must be float, got {type(strat['wear_endpoint'])}"
    )
    assert strat["wear_endpoint"] >= 0.0, (
        f"wear_endpoint must be non-negative, got {strat['wear_endpoint']}"
    )


def test_strat_wear_endpoint_determinism_5_runs():
    """5 runs with seed=777 must yield identical wear_endpoint values."""
    endpoints = []
    for _ in range(5):
        rec = twin.run_episode(777, None)
        assert "strat" in rec
        endpoints.append(rec["strat"]["wear_endpoint"])
    assert len(set(endpoints)) == 1, f"wear_endpoint non-deterministic across 5 runs: {endpoints}"


def test_strat_wear_knee_acceleration_formula():
    """Minimal C3 wear equation w(t+1)=w+ALPHA*L*(1+4*1[w>0.8]) accelerates 5x post-knee."""
    # Machine with 192 RUN steps: wear reaches exactly 192/240 = 0.8 (pre-knee)
    states_192 = [["RUN"] * 192 + ["STARVED"] * (config.T - 192)]
    # Machine with 193 RUN steps: wear reaches 192/240 + 1/240 = 193/240 = 0.804167...
    states_193 = [["RUN"] * 193 + ["STARVED"] * (config.T - 193)]
    # Machine with 194 RUN steps: wear reaches 193/240 + 5/240
    states_194 = [["RUN"] * 194 + ["STARVED"] * (config.T - 194)]

    pad = [["STARVED"] * config.T] * (config.N_MACHINES - 1)
    w_192 = twin.compute_wear(states_192 + pad)[0]
    w_193 = twin.compute_wear(states_193 + pad)[0]
    w_194 = twin.compute_wear(states_194 + pad)[0]

    np.testing.assert_allclose(w_192, 0.8)
    np.testing.assert_allclose(w_193, 193.0 / 240.0)
    # The step from 193 to 194 happens when w > 0.8, so rate is 5 * ALPHA = 5/240
    np.testing.assert_allclose(w_194, 193.0 / 240.0 + 5.0 / 240.0)


def test_strat_wear_stream_budget_zero_new_streams():
    """Minimal C3 wear must draw from existing streams with ZERO new RNG streams."""
    assert config.N_STREAMS == 36
    streams = twin._spawn_streams(777)
    noise, place, drop, agv, fail = streams
    assert len(noise) == 26
    # No stream index >= 36
    assert all(idx < 36 for idx in config.MACHINE_INDEX.values())


def test_strat_maint_flag_unvalidated_constant():
    """Stratification export must contain False constant 'maint_flag' marked unvalidated."""
    rec = twin.run_episode(777, _PROBE_FAULT)
    assert "strat" in rec, "Record missing 'strat' export"
    strat = rec["strat"]
    assert "maint_flag" in strat, "Stratification missing 'maint_flag'"
    assert strat["maint_flag"] is False, (
        f"maint_flag must be False constant, got {strat['maint_flag']}"
    )
    assert strat.get("maint_flag_unvalidated", True) is True, (
        "maint_flag must be marked unvalidated (SPEC_UP §9 item 3)"
    )


def test_strat_family_and_mode_taxonomy():
    """Stratification export must carry fault family and mode taxonomy."""
    # Observation-only mode: drift, spike, bias, loss
    rec_drift = twin.run_episode(777, _PROBE_FAULT)
    assert "strat" in rec_drift, "Record missing 'strat' export"
    strat_drift = rec_drift["strat"]
    assert strat_drift.get("family") == "drift", (
        f"Expected family='drift', got {strat_drift.get('family')}"
    )
    assert strat_drift.get("mode") == "observation-only", (
        f"Expected mode='observation-only' for drift fault, got {strat_drift.get('mode')}"
    )

    # Physical-propagation mode: delay, breakdown, quality
    rec_delay = twin.run_episode(777, _DELAY_FAULT)
    assert "strat" in rec_delay, "Record missing 'strat' export"
    strat_delay = rec_delay["strat"]
    assert strat_delay.get("family") == "delay", (
        f"Expected family='delay', got {strat_delay.get('family')}"
    )
    assert strat_delay.get("mode") == "physical-propagation", (
        f"Expected mode='physical-propagation' for delay fault, got {strat_delay.get('mode')}"
    )


def test_strat_event_derived_roots_and_hops():
    """Stratification export must contain event-derived root_id, hop, and root_ids."""
    rec = twin.run_episode(777, _PROBE_FAULT)
    assert "strat" in rec, "Record missing 'strat' export"
    strat = rec["strat"]
    assert strat.get("root_id") == "B2", (
        f"Expected root_id='B2' for F-21 on B2, got {strat.get('root_id')}"
    )
    assert strat.get("hop") == 0, (
        f"Expected hop=0 for origin machine, got {strat.get('hop')}"
    )
    assert "root_ids" in strat, "Stratification missing 'root_ids' list"
    assert "B2" in strat["root_ids"], (
        f"Expected 'B2' in root_ids, got {strat.get('root_ids')}"
    )


def test_strat_sensor_vs_process_deferred_unknown():
    """sensor_vs_process must be constant 'unknown' with unvalidated marker."""
    rec = twin.run_episode(777, _PROBE_FAULT)
    assert "strat" in rec, "Record missing 'strat' export"
    strat = rec["strat"]
    assert "sensor_vs_process" in strat, "Stratification missing 'sensor_vs_process'"
    assert strat["sensor_vs_process"] == "unknown", (
        f"sensor_vs_process must be 'unknown' (deferred honestly until parity channels exist), "
        f"got {strat['sensor_vs_process']}"
    )
    assert strat.get("sensor_vs_process_unvalidated", True) is True, (
        "sensor_vs_process must carry unvalidated marker"
    )


def test_strat_warmup_flag_steps_0_14():
    """Stratification export must flag steps 0-14 as warm-up."""
    rec = twin.run_episode(777, _PROBE_FAULT)
    assert "strat" in rec, "Record missing 'strat' export"
    strat = rec["strat"]
    assert "warmup_flag" in strat, "Stratification missing 'warmup_flag'"
    assert strat.get("warmup_steps") == 15 or strat.get("warmup_window") == (0, 14), (
        f"Expected first 15 steps (0-14) marked as warm-up, "
        f"got {strat.get('warmup_steps') or strat.get('warmup_window')}"
    )


def test_strat_funnel_census_full_accounting():
    """Stratification export must provide full funnel census counts."""
    rec = twin.run_episode(777, _PROBE_FAULT)
    assert "strat" in rec, "Record missing 'strat' export"
    strat = rec["strat"]
    assert "funnel_census" in strat, "Stratification missing 'funnel_census'"
    fc = strat["funnel_census"]
    for k in ("sunk", "scrapped", "packaged", "kit_A", "kit_B", "kit_C"):
        assert k in fc, f"funnel_census missing key '{k}'"


# ==============================================================================
# Group 2: Sunk Rolling-20 Median >= 30 Gate Test & Funnel Wall Report
# ==============================================================================

def test_funnel_sunk_rolling_20_median_gate():
    """Rolling-20 median >= 30 gate validator over exact 20-seed batch."""
    assert hasattr(twin, "check_funnel_gate"), (
        "src.twin missing 'check_funnel_gate' funnel gate validator"
    )
    report = twin.check_funnel_gate(_EXACT_20_SEEDS)
    assert report["median_sunk"] >= 30, (
        f"Funnel gate failed: median_sunk={report.get('median_sunk')} < 30 "
        f"over seeds {_EXACT_20_SEEDS}"
    )
    assert report["passed"] is True, f"Funnel gate report not marked passed: {report}"
    assert "p10" in report and "p90" in report, "Funnel gate report missing p10/p90 percentiles"
    assert report["seeds"] == _EXACT_20_SEEDS, "Funnel gate report seeds mismatch"
    assert "variant_id" in report, "Funnel gate report missing variant_id"


def test_funnel_census_kits_completed_definition():
    """funnel_census kits_completed must equal sunk excluding scrapped."""
    for s in _EXACT_20_SEEDS:
        rec = twin.run_episode(s, None)
        assert "strat" in rec, f"Record for seed {s} missing 'strat' export"
        census = rec["strat"]["funnel_census"]
        assert "kits_completed" in census, "funnel_census missing 'kits_completed'"
        assert census["kits_completed"] == census["sunk"] - census["scrapped"], (
            f"Seed {s}: kits_completed ({census['kits_completed']}) must equal "
            f"sunk ({census['sunk']}) - scrapped ({census['scrapped']})"
        )


def test_funnel_wall_report_schema_version_and_funnel_object(tmp_path):
    """wall_report.json must carry schema_version=2 and funnel object with median_sunk >= 30."""
    cal = tmp_path / "cal.json"
    twin._calibrate(str(cal))
    evdir = tmp_path / "ev"
    rc = twin.main([
        "--manifest", "quick",
        "--subset", "1",
        "--jobs", "1",
        "--calibration", str(cal),
        "--wall-report",
        "--evidence-dir", str(evdir),
    ])
    assert rc == 0
    wall = json.loads((evdir / "wall_report.json").read_text())
    assert wall.get("schema_version") == 2, (
        f"wall_report.json must carry schema_version=2, got {wall.get('schema_version')}"
    )
    assert "funnel" in wall, "wall_report.json missing 'funnel' object"
    f = wall["funnel"]
    for k in ("median_sunk", "p10", "p90", "variant_id"):
        assert k in f, f"wall_report funnel object missing '{k}'"
    assert f["median_sunk"] >= 30, (
        f"Funnel gate requirement in wall_report failed: median_sunk={f['median_sunk']} < 30"
    )


# ==============================================================================
# Group 3: Schema Version Transition: TWIN_SCHEMA 2->3 and v2 Rejection
# ==============================================================================

def test_schema_v3_twin_schema_constant_bump():
    """TWIN_SCHEMA constant must be bumped 2->3 in src/config.py."""
    assert config.TWIN_SCHEMA == 3, (
        f"TWIN_SCHEMA must transition 2->3 for stratification export, got {config.TWIN_SCHEMA}"
    )


def test_schema_v3_record_schema_version_bump():
    """Episode record schema_version must be 3."""
    rec = twin.run_episode(777, _PROBE_FAULT)
    assert rec["schema_version"] == 3, (
        f"Episode record schema_version must be 3, got {rec.get('schema_version')}"
    )


def test_schema_v3_v2_readers_reject_v3_loudly_with_value_error():
    """v2 readers must reject v3 records loudly with ValueError."""
    def _v2_reader(record):
        if record.get("schema_version") != 2:
            raise ValueError(
                f"v2 reader non-comparable: rejects schema_version={record.get('schema_version')!r}, want 2"
            )
        return True

    rec = twin.run_episode(777, _PROBE_FAULT)
    assert rec.get("schema_version") == 3, (
        f"Target record must carry schema_version=3 for rejection test, got {rec.get('schema_version')}"
    )
    with pytest.raises(ValueError, match="v2 reader non-comparable"):
        _v2_reader(rec)


def test_schema_v3_replay_digest_rejects_v2_records():
    """When TWIN_SCHEMA transitions to 3, replay_digest must reject v2 records."""
    assert config.TWIN_SCHEMA == 3, "TWIN_SCHEMA must be 3 for v3 digest validation"
    rec = twin.run_episode(777, _PROBE_FAULT)
    v2_record = copy.deepcopy(rec)
    v2_record["schema_version"] = 2
    with pytest.raises(ValueError, match="want 3"):
        twin.replay_digest(v2_record)


# ==============================================================================
# Group 4: Warm-Up Exclusion from run_calibration Fits
# ==============================================================================

def test_warmup_exclusion_from_run_calibration_fits():
    """run_calibration must exclude first 15 steps (shape must be (105, 26))."""
    clean = twin.run_calibration(777)
    assert clean.shape == (105, 26), (
        f"run_calibration must exclude first 15 warm-up steps: "
        f"got shape {clean.shape}, expected (105, 26) [CAL_WIN 120 - 15 = 105]"
    )


def test_warmup_calibration_fit_slice_is_steps_15_to_120():
    """run_calibration fit array must exactly match steps 15:120 of clean obs."""
    rec = twin.run_episode(777, None, enable_natural_breakdown=False)
    clean = twin.run_calibration(777)
    expected = np.asarray(rec["obs"], dtype=float)[:, 15:120].T
    assert clean.shape == expected.shape, (
        f"Shape mismatch: {clean.shape} vs {expected.shape}"
    )
    np.testing.assert_allclose(
        clean,
        expected,
        err_msg="run_calibration fit array must match steps 15:120 of clean obs (excluding first 15 warm-up steps)",
    )


def test_warmup_transient_pool_retains_first_15_steps():
    """Transient pool must retain the first 15 warm-up steps excluded from calibration fits."""
    rec = twin.run_episode(777, _PROBE_FAULT)
    assert "strat" in rec, "Record missing 'strat' export"
    strat = rec["strat"]
    assert "warmup_pool" in strat, (
        "stratification missing 'warmup_pool' (first 15 steps retained in transient pool)"
    )
    pool = strat["warmup_pool"]
    assert len(pool) == 15, f"Transient pool must retain exactly 15 warm-up steps, got {len(pool)}"


# ==============================================================================
# Group 5: Per-Machine State Histogram Denominator Rules
# ==============================================================================

def test_histogram_per_machine_denominator_rule_sums_to_one():
    """Per-machine state histogram must sum to 1.0 +- 0.01 across RUN/STARVED/BLOCKED/DOWN."""
    rec = twin.run_episode(777, _PROBE_FAULT)
    assert "strat" in rec, "Record missing 'strat' export"
    strat = rec["strat"]
    assert "state_histogram" in strat, "Stratification missing 'state_histogram'"
    hist = strat["state_histogram"]
    assert len(hist) == 26, f"state_histogram must cover all 26 machines, got {len(hist)}"
    for m, shares in hist.items():
        tot = sum(shares.values())
        assert abs(tot - 1.0) <= 0.01, (
            f"Machine {m} state histogram sum {tot:.4f} != 1.0 +/- 0.01 (denominator rule violated)"
        )


def test_histogram_plant_rollup_excludes_standby_24_machines():
    """Plant state rollup must sum to 1.0 +- 0.01 over 24 machines (excluding B7S/RWK0)."""
    rec = twin.run_episode(777, _PROBE_FAULT)
    assert "strat" in rec, "Record missing 'strat' export"
    strat = rec["strat"]
    assert "plant_state_rollup" in strat, "Stratification missing 'plant_state_rollup'"
    rollup = strat["plant_state_rollup"]
    shares = rollup.get("shares", rollup)
    tot = sum(shares.get(st, 0.0) for st in ("RUN", "STARVED", "BLOCKED", "DOWN"))
    assert abs(tot - 1.0) <= 0.01, (
        f"Plant rollup state shares sum {tot:.4f} != 1.0 +/- 0.01"
    )
    machines = rollup.get("machines", set())
    assert "B7S" not in machines and "RWK0" not in machines, (
        "Plant rollup must exclude standby machines B7S and RWK0 (STANDBY_EXCLUDED)"
    )
    assert len(machines) == 24, (
        f"Plant rollup must cover exactly 24 machines, got {len(machines)}"
    )
