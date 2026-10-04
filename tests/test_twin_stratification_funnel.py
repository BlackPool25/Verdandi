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
    7,
    11,
    13,
    42,
    777,
    1234,
    999,
    2026,
    12345,
    1001,
    1002,
    1003,
    1004,
    1005,
    1006,
    1007,
    1008,
    1009,
    1010,
    1011,
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
        "has_warmup_period",
        "funnel_census",
    }
    missing = required_keys - set(strat.keys())
    assert not missing, (
        f"Stratification export missing required keys: {sorted(missing)}"
    )


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
    assert len(set(endpoints)) == 1, (
        f"wear_endpoint non-deterministic across 5 runs: {endpoints}"
    )


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
    noise, _place, _drop, _agv, _fail, _eta = streams
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
    """Stratification export must flag steps 0-14 as warm-up via has_warmup_period."""
    rec = twin.run_episode(777, _PROBE_FAULT)
    assert "strat" in rec, "Record missing 'strat' export"
    strat = rec["strat"]
    assert "has_warmup_period" in strat, "Stratification missing 'has_warmup_period'"
    assert strat["has_warmup_period"] is True
    assert "is_warmup_episode" in strat, "Stratification missing 'is_warmup_episode'"
    assert strat["is_warmup_episode"] is True
    assert "warmup_flag" not in strat, "Old episode key 'warmup_flag' must be renamed"
    assert "is_warmup" not in strat, "Old episode key 'is_warmup' must be renamed"
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
    assert "p10" in report and "p90" in report, (
        "Funnel gate report missing p10/p90 percentiles"
    )
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
    rc = twin.main(
        [
            "--manifest",
            "quick",
            "--subset",
            "1",
            "--jobs",
            "1",
            "--calibration",
            str(cal),
            "--wall-report",
            "--evidence-dir",
            str(evdir),
        ]
    )
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


def test_funnel_wall_report_partial_schema_version_and_funnel_object(tmp_path):
    """Partial wall_report.json must carry schema_version=2 and funnel object."""
    import argparse

    evdir = tmp_path / "ev_partial"
    args = argparse.Namespace(
        wall_report=True,
        evidence_dir=str(evdir),
        jobs=1,
    )
    manifest = twin.build_faults(12345)[:2]
    twin._write_partial(args, manifest, [], 12345, 0.04, 600.0)
    wall = json.loads((evdir / "wall_report.json").read_text())
    assert wall.get("schema_version") == 2, (
        f"Partial wall_report.json must carry schema_version=2, got {wall.get('schema_version')}"
    )
    assert wall.get("partial") is True
    assert "funnel" in wall, "Partial wall_report.json missing 'funnel' object"
    f = wall["funnel"]
    for k in ("median_sunk", "p10", "p90", "variant_id"):
        assert k in f, f"Partial wall_report funnel object missing '{k}'"
    assert f["median_sunk"] >= 30


# ==============================================================================
# Group 3: Schema Version Transition: TWIN_SCHEMA 3->4 and v2/v3 Rejection
# ==============================================================================


@pytest.mark.skipif(
    config.TWIN_SCHEMA < 3,
    reason="TWIN_SCHEMA 2->3 bump belongs to Todo 5 / Todo 9 flag-day migration",
)
def test_schema_v4_twin_schema_constant_bump():
    """TWIN_SCHEMA constant must be bumped >= 4 in src/config.py."""
    assert config.TWIN_SCHEMA >= 4, (
        f"TWIN_SCHEMA must be >= 4, got {config.TWIN_SCHEMA}"
    )


@pytest.mark.skipif(
    config.TWIN_SCHEMA < 3,
    reason="TWIN_SCHEMA 2->3 bump belongs to Todo 5 / Todo 9 flag-day migration",
)
def test_schema_v4_record_schema_version_bump():
    """Episode record schema_version must match config.TWIN_SCHEMA."""
    rec = twin.run_episode(777, _PROBE_FAULT)
    assert rec["schema_version"] == config.TWIN_SCHEMA, (
        f"Episode record schema_version must be {config.TWIN_SCHEMA}, got {rec.get('schema_version')}"
    )


@pytest.mark.skipif(
    config.TWIN_SCHEMA < 3,
    reason="TWIN_SCHEMA 2->3 bump belongs to Todo 5 / Todo 9 flag-day migration",
)
def test_schema_v4_v2_readers_reject_v4_loudly_with_value_error():
    """v2 readers must reject v4+ records loudly with ValueError."""

    def _v2_reader(record):
        if record.get("schema_version") != 2:
            raise ValueError(
                f"v2 reader non-comparable: rejects schema_version={record.get('schema_version')!r}, want 2"
            )
        return True

    rec = twin.run_episode(777, _PROBE_FAULT)
    assert rec.get("schema_version") == config.TWIN_SCHEMA, (
        f"Target record must carry schema_version={config.TWIN_SCHEMA} for rejection test, got {rec.get('schema_version')}"
    )
    with pytest.raises(ValueError, match="v2 reader non-comparable"):
        _v2_reader(rec)


@pytest.mark.skipif(
    config.TWIN_SCHEMA < 3,
    reason="TWIN_SCHEMA 2->3 bump belongs to Todo 5 / Todo 9 flag-day migration",
)
def test_schema_v4_replay_digest_rejects_v2_records():
    """When TWIN_SCHEMA transitions to 4+, replay_digest must reject v2 records."""
    assert config.TWIN_SCHEMA >= 4, "TWIN_SCHEMA must be >= 4 for digest validation"
    rec = twin.run_episode(777, _PROBE_FAULT)
    v2_record = copy.deepcopy(rec)
    v2_record["schema_version"] = 2
    with pytest.raises(ValueError, match=f"want {config.TWIN_SCHEMA}"):
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
    assert len(pool) == 15, (
        f"Transient pool must retain exactly 15 warm-up steps, got {len(pool)}"
    )


def test_transient_pool_alias_kill_and_channels():
    """Transient pool must be a separate object from warmup_pool with all 5 channels."""
    rec = twin.run_episode(777, None)
    strat = rec["strat"]
    assert "warmup_pool" in strat and "transient_pool" in strat
    assert strat["warmup_pool"] is not strat["transient_pool"]
    val_before = strat["transient_pool"][0][0]
    strat["warmup_pool"][0][0] = 99999.0
    assert strat["transient_pool"][0][0] == val_before, (
        "Mutation in warmup_pool affected transient_pool (alias not killed)"
    )
    assert "transient_channels" in strat
    tc = strat["transient_channels"]
    for ch in ("observations", "states", "buffers", "throughput", "currents"):
        assert ch in tc, f"transient_channels missing channel '{ch}'"
        assert len(tc[ch][0]) == 15, f"Channel '{ch}' first row length != 15"


def test_stationarity_probe_record_only():
    """probe_stationarity computes metric deltas over steps 0-14 vs 15-29 without gating."""
    rec = twin.run_episode(777, None)
    probe = twin.probe_stationarity(rec)
    for k in (
        "transient_starved_share",
        "post_starved_share",
        "starved_delta",
        "transient_buffer_mean",
        "post_buffer_mean",
        "buffer_delta",
    ):
        assert k in probe, f"probe_stationarity missing key '{k}'"
    assert "stationarity_probe" in rec["strat"]


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
    assert len(hist) == 26, (
        f"state_histogram must cover all 26 machines, got {len(hist)}"
    )
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


def test_variant_state_histograms_masked_with_warmup():
    """Variant path masks state_histograms and plant rollup with warmup_mask (denom 285)."""
    rec_var = twin.run_episode(777, None, variant="ladder-budget-warmup-v1")
    s_var = rec_var["strat"]
    hist = s_var["state_histograms"]
    assert len(hist) == 26
    for m, shares in hist.items():
        tot = sum(shares.values())
        assert abs(tot - 1.0) <= 0.01, f"Variant machine {m} state histogram sum {tot} != 1.0"
    rollup = s_var["plant_state_rollup"]
    tot_plant = sum(rollup["shares"].values())
    assert abs(tot_plant - 1.0) <= 0.01


def test_baseline_state_histograms_unmasked_denominator_300():
    """Baseline path retains unmasked histograms with denominator 300 (zero baseline reds)."""
    rec = twin.run_episode(777, None)
    s = rec["strat"]
    # Pinned golden baseline values for seed 777
    assert s["plant_state_rollup"]["shares"]["RUN"] == 0.8573611111111111
    assert s["plant_state_rollup"]["shares"]["DOWN"] == 0.015277777777777777
    assert s["plant_state_rollup"]["shares"]["STARVED"] == 0.12736111111111112
    assert s["state_histograms"]["ASM0"]["RUN"] == 0.7733333333333333
    assert s["state_histograms"]["ASM0"]["STARVED"] == 0.22666666666666666


# ==============================================================================
# Group 6: Gated Buffer Unfreeze and AGV-Priority Variants (Todo 6)
# ==============================================================================


def test_buffer_unfreeze_listed_bottlenecks_allowed_only():
    """ONLY listed bottleneck buffers are in ALLOWED_UNFREEZE_BUFFERS with documented caps."""
    expected_allowed = {
        "GA9",
        "GB9",
        "_C7TAIL",
        "C7PKG",
        "C67",
        "A89",
        "B89",
        "A78",
        "B7PB8",
        "B7SB8",
        "ASM01",
        "INSP01",
        "INSP02",
        "RWK_RET",
    }
    assert config.ALLOWED_UNFREEZE_BUFFERS == expected_allowed, (
        f"Mismatch in ALLOWED_UNFREEZE_BUFFERS: {config.ALLOWED_UNFREEZE_BUFFERS ^ expected_allowed}"
    )

    # Strictly unlisted buffers must NEVER be allowed
    for unlisted in (
        "A01",
        "A12",
        "A27",
        "B01",
        "B12",
        "B2B7P",
        "B2B7S",
        "C01",
        "C12",
        "C26",
        "PKG01",
        "PKG02",
        "SBUF",
    ):
        assert unlisted not in config.ALLOWED_UNFREEZE_BUFFERS, (
            f"Unlisted buffer {unlisted} must be frozen"
        )

    # Verify explicit old -> new caps documented in config
    assert config.UNFROZEN_BUFFER_CAPS["GA9"] == 20  # old: 15
    assert config.UNFROZEN_BUFFER_CAPS["GB9"] == 20  # old: 15
    assert config.UNFROZEN_BUFFER_CAPS["_C7TAIL"] == 20  # old: 15
    assert config.UNFROZEN_BUFFER_CAPS["C7PKG"] == 20  # old: 15
    assert config.UNFROZEN_BUFFER_CAPS["C67"] == 20  # old: 15
    assert config.UNFROZEN_BUFFER_CAPS["A89"] == 20  # old: 15
    assert config.UNFROZEN_BUFFER_CAPS["B89"] == 20  # old: 15
    assert config.UNFROZEN_BUFFER_CAPS["A78"] == 20  # old: 15
    assert config.UNFROZEN_BUFFER_CAPS["B7PB8"] == 30  # old: 25
    assert config.UNFROZEN_BUFFER_CAPS["B7SB8"] == 30  # old: 25
    assert config.UNFROZEN_BUFFER_CAPS["ASM01"] == 30  # old: 25
    assert config.UNFROZEN_BUFFER_CAPS["INSP01"] == 30  # old: 25
    assert config.UNFROZEN_BUFFER_CAPS["INSP02"] == 30  # old: 25
    assert config.UNFROZEN_BUFFER_CAPS["RWK_RET"] == 15  # old: 10


def test_buffer_unfreeze_unlisted_buffer_rejected_by_gate():
    """Unlisted buffer modifications must be strictly rejected by check_variant_gate."""
    unlisted_variant = {
        "variant_id": "bad-unlisted-variant",
        "buffer_caps": {"A01": 50},  # A01 is frozen, not in ALLOWED_UNFREEZE_BUFFERS
    }
    report = twin.check_variant_gate(unlisted_variant, seeds=[777])
    assert report["passed"] is False, "Unlisted buffer modification must NOT pass gate"
    assert report["rejected"] is True
    assert "unlisted" in report["reason"].lower()
    assert "A01" in report["unlisted_buffers"]

    # In strict mode, an exception must be raised
    with pytest.raises(ValueError, match="unlisted buffer modification"):
        twin.check_variant_gate(unlisted_variant, seeds=[777], strict=True)


def test_pileup_violations_excessive_buffer_change_rejected_by_gate(monkeypatch):
    """A variant causing pileup violations must be strictly rejected by the variant gate."""
    test_variant = {
        "variant_id": "pileup-reject-test",
        "buffer_caps": {"GA9": 20},
    }
    mock_violation = [
        {"buffer": "GA9", "downstream": "ASM0", "start": 40, "length": 35}
    ]

    # Mock duty_cycle to simulate a pileup violation
    real_duty_cycle = twin.duty_cycle

    def _mock_duty(rec):
        d = real_duty_cycle(rec)
        d["pileup_violations"] = mock_violation
        return d

    monkeypatch.setattr(twin, "duty_cycle", _mock_duty)

    report = twin.check_variant_gate(test_variant, seeds=[777])
    assert report["passed"] is False, (
        "Variant with pileup violations must NOT pass gate"
    )
    assert report["rejected"] is True
    assert "pileup" in report["reason"].lower()
    assert report["pileup_violations"] == mock_violation

    # In strict mode, ValueError must be raised
    with pytest.raises(ValueError, match="pileup violations detected"):
        twin.check_variant_gate(test_variant, seeds=[777], strict=True)


def test_agv_priority_variants_registered_and_clean_on_seed_777():
    """All registered AGV-priority variants must pass gate on seed 777 with zero pileup violations."""
    variants = [
        "baseline",
        "agv-priority-starvation",
        "agv-priority-seeded",
        "agv-priority-rework",
        "bottleneck-unfreeze",
        "rebalanced-funnel-v1",
        "rebalanced-funnel-seeded",
    ]
    for var_id in variants:
        assert var_id in config.FUNNEL_VARIANTS, (
            f"Variant {var_id} not registered in FUNNEL_VARIANTS"
        )
        report = twin.check_variant_gate(var_id, seeds=[777])
        assert report["passed"] is True, f"Variant {var_id} failed gate: {report}"
        assert len(report["pileup_violations"]) == 0, (
            f"Variant {var_id} had pileup violations: {report}"
        )
        assert report["median_sunk"] >= 30, (
            f"Variant {var_id} median sunk < 30: {report['median_sunk']}"
        )


def test_seed_777_pileup_clean_and_passes_gate():
    """Seed 777 must have zero pileup violations in duty_cycle and pass the variant gate."""
    rec = twin.run_episode(777, None)
    dc = twin.duty_cycle(rec)
    assert len(dc["pileup_violations"]) == 0, (
        f"Seed 777 had pileup violations: {dc['pileup_violations']}"
    )
    assert len(rec.get("pileup_violations", [])) == 0
    report = twin.check_variant_gate("baseline", seeds=[777])
    assert report["passed"] is True
    assert report["pileup_violations"] == []


def test_agv_priority_ordering_seeded_and_starvation_execution():
    """AGV-priority variants must execute deterministically without stream corruption."""
    rec1 = twin.run_episode(777, None, variant="agv-priority-seeded")
    rec2 = twin.run_episode(777, None, variant="agv-priority-seeded")
    assert rec1["flow_stats"]["sunk"] == rec2["flow_stats"]["sunk"]
    assert rec1["states"] == rec2["states"]

    rec_starve = twin.run_episode(777, None, variant="agv-priority-starvation")
    assert rec_starve["flow_stats"]["sunk"] >= 30
    dc = twin.duty_cycle(rec_starve)
    assert len(dc["pileup_violations"]) == 0


def test_buffer_unfreeze_and_agv_priority_20_seeds_gate():
    """Rebalanced funnel variant must achieve rolling median sunk >= 30 across 20 seeds with 0 pileups."""
    report = twin.check_variant_gate("rebalanced-funnel-v1", seeds=_EXACT_20_SEEDS)
    assert report["passed"] is True, f"20-seed gate failed: {report}"
    assert len(report["pileup_violations"]) == 0, (
        f"20-seed gate had pileup violations: {report}"
    )
    assert report["median_sunk"] >= 30, (
        f"20-seed median sunk < 30: {report['median_sunk']}"
    )
    assert report["p10"] > 0
    assert report["p90"] >= report["median_sunk"]
