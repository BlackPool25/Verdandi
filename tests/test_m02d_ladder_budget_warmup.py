"""M0.2d magnitude ladder, rate budget, and warm-up contract test suite.

Dual-marked with k3 and battery per C2. Covers:
1. Multi-seed variant determinism (new-vs-new across 5 seeds).
2. Variant ladder rung assignment and builder contracts.
3. Honest rate budget (union-over-t, extended-DOWN, breach vs pass).
4. Twin warm-up repair & pools (alias kill, key renames, masked strat, stationarity probe).
5. Downstream graded severity (variant distinguishes, baseline frozen).
6. Adversarial magnitude bounds & branch coverage.
7. Evidence provenance and dataset filter contract.
8. Non-vacuity failure probes.
"""

from __future__ import annotations

import copy
import json
import math
import pathlib

import pandas as pd
import pytest

from src import calibrate, config, dataset_export, evidence, twin

pytestmark = [pytest.mark.k3, pytest.mark.battery]


# ---------------------------------------------------------------------------
# 1. Multi-seed determinism
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("seed", [7, 42, 777, 999, 1234])
def test_multi_seed_variant_determinism(seed: int) -> None:
    """Verifies replay_digest and state/observation equality on repeated variant runs.

    Tests new-vs-new variant determinism (not golden pins).
    """
    fault = {
        "id": "F-21",
        "class": "drift",
        "origin": "B2",
        "t0": 150,
        "dur": 12,
        "mag_sigma": 2.5,
    }
    rec1 = twin.run_episode(seed, copy.deepcopy(fault), variant=config.VARIANT_ID)
    rec2 = twin.run_episode(seed, copy.deepcopy(fault), variant=config.VARIANT_ID)

    assert twin.replay_digest(rec1) == twin.replay_digest(rec2)
    assert rec1["obs"] == rec2["obs"]
    assert rec1["states"] == rec2["states"]
    assert rec1["parts"] == rec2["parts"]
    assert rec1["strat"]["kit_sev_max"] == rec2["strat"]["kit_sev_max"]
    assert rec1["strat"]["state_histograms"] == rec2["strat"]["state_histograms"]


# ---------------------------------------------------------------------------
# 2. Variant ladder rung assignment & builder
# ---------------------------------------------------------------------------


def test_variant_ladder_builder_share_and_rep_invariants() -> None:
    """Variant builder achieves >=20% incipient share on 175 randomizable rows,
    keeps all rep rows caricature (mag_sigma >= 4.0), and populates mag_rung & sev."""
    rows = twin.build_faults_variant(12345)
    assert len(rows) == 182

    # 175 randomizable rows (rep=False)
    non_rep = [r for r in rows if not r.get("rep")]
    assert len(non_rep) == 175

    incipient = [r for r in non_rep if r["mag_rung"] == "incipient"]
    incipient_share = len(incipient) / len(non_rep)
    assert incipient_share >= config.INCIPIENT_SHARE  # >= 0.20

    # 7 rep rows (fixed oracle representative pins)
    rep_rows = [r for r in rows if r.get("rep")]
    assert len(rep_rows) == 7
    for r in rep_rows:
        assert r["mag_rung"] == "caricature"
        assert r["mag_sigma"] >= 4.0
        assert r["sev"] == r["mag_sigma"]

    # Every variant row has 'mag_rung' and 'sev' == 'mag_sigma'
    for r in rows:
        assert "mag_rung" in r
        assert "sev" in r
        assert r["sev"] == r["mag_sigma"]
        if r["mag_rung"] == "incipient":
            assert (
                config.MAG_LADDER["incipient"][0]
                <= r["mag_sigma"]
                <= config.MAG_LADDER["incipient"][1]
            )
        elif r["mag_rung"] == "caricature":
            assert (
                config.MAG_LADDER["caricature"][0]
                <= r["mag_sigma"]
                <= config.MAG_LADDER["caricature"][1]
            )


def test_variant_ladder_non_signal_low_rung_params() -> None:
    """Non-signal incipient rows have low-rung parameters."""
    rows = twin.build_faults_variant(12345)
    non_rep_incipient = [
        r for r in rows if not r.get("rep") and r["mag_rung"] == "incipient"
    ]
    assert len(non_rep_incipient) > 0

    seen_classes = set()
    for r in non_rep_incipient:
        cls = r["class"]
        extra = r.get("extra", {})
        if cls == "delay":
            seen_classes.add(cls)
            assert extra.get("d") in {
                config.LOW_RUNG_DELAY_D[0],
                config.LOW_RUNG_DELAY_D[1],
            }
        elif cls == "loss":
            seen_classes.add(cls)
            assert (
                config.LOW_RUNG_DROP_RATE[0]
                <= extra.get("drop_rate", 0.0)
                <= config.LOW_RUNG_DROP_RATE[1]
            )
        elif cls == "breakdown":
            seen_classes.add(cls)
            assert (
                config.LOW_RUNG_MTTR_MULT[0]
                <= extra.get("mttr_mult", 0.0)
                <= config.LOW_RUNG_MTTR_MULT[1]
            )
        elif cls == "quality":
            seen_classes.add(cls)
            assert (
                config.LOW_RUNG_REJECT_RATE[0]
                <= extra.get("reject_rate", 0.0)
                <= config.LOW_RUNG_REJECT_RATE[1]
            )

    # Verify that all 4 non-signal classes are present among incipient rows
    assert seen_classes.issuperset({"delay", "loss", "breakdown", "quality"})


def test_variant_builder_caps_budget_and_validates_clean() -> None:
    """Variant builder with cap_budget=True produces rows with dur <= 14 and dur*mult <= 14."""
    rows = twin.build_faults_variant(12345, cap_budget=True)
    assert len(rows) == 182
    for r in rows:
        if not r.get("rep"):
            assert r["dur"] <= 14
            if r["class"] == "breakdown":
                mult = r.get("extra", {}).get("mttr_mult", 1.0)
                assert r["dur"] * math.ceil(mult) <= 14


# ---------------------------------------------------------------------------
# 3. Honest rate budget
# ---------------------------------------------------------------------------


def test_rate_budget_15_step_drift_raises() -> None:
    """15-step drift raises ValueError naming union and allowed counts."""
    specs = [{"origin": "B2", "class": "drift", "t0": 150, "dur": 15, "extra": {}}]
    with pytest.raises(ValueError) as excinfo:
        twin.check_rate_budget(specs, scored=180)
    err_msg = str(excinfo.value)
    assert "fault rate budget exceeded" in err_msg
    assert "union 15" in err_msg
    assert "allowed 14.4" in err_msg


def test_rate_budget_24_step_extended_breakdown_raises() -> None:
    """24-step extended breakdown (dur=12, mttr_mult=2.0) raises ValueError."""
    specs = [
        {
            "origin": "B2",
            "class": "breakdown",
            "t0": 150,
            "dur": 12,
            "extra": {"mttr_mult": 2.0},
        }
    ]
    with pytest.raises(ValueError) as excinfo:
        twin.check_rate_budget(specs, scored=180)
    err_msg = str(excinfo.value)
    assert "fault rate budget exceeded" in err_msg
    assert "union 24" in err_msg
    assert "allowed 14.4" in err_msg


def test_rate_budget_12_step_drift_passes() -> None:
    """12-step drift passes rate budget check silently and computes steps correctly."""
    specs = [{"origin": "B2", "class": "drift", "t0": 150, "dur": 12, "extra": {}}]
    twin.check_rate_budget(specs, scored=180)
    union_steps, machine_steps = twin.fault_steps(specs)
    assert union_steps == 12
    assert machine_steps == 12


def test_rate_budget_overlapping_faults_union_and_machine_steps() -> None:
    """Two overlapping faults compute union and machine steps correctly."""
    # Fault 1: steps [150, 160) -> 10 steps
    # Fault 2: steps [155, 165) -> 10 steps
    # Union is [150, 165) -> 15 steps; machine_steps is 10 + 10 = 20 steps
    f1 = {"origin": "B2", "class": "drift", "t0": 150, "dur": 10, "extra": {}}
    f2 = {"origin": "C1", "class": "drift", "t0": 155, "dur": 10, "extra": {}}
    union_steps, machine_steps = twin.fault_steps([f1, f2])
    assert union_steps == 15
    assert machine_steps == 20

    # Overlapping breakdown:
    # Breakdown on B2: t0=150, dur=6, mttr_mult=1.5 -> ceil(6*1.5)=9 steps -> [150, 159)
    # Drift on B5: t0=155, dur=5 -> steps [155, 160)
    # Union is [150, 160) = 10 steps; machine_steps is 9 + 5 = 14 steps
    fb = {
        "origin": "B2",
        "class": "breakdown",
        "t0": 150,
        "dur": 6,
        "extra": {"mttr_mult": 1.5},
    }
    fd = {"origin": "B5", "class": "drift", "t0": 155, "dur": 5, "extra": {}}
    u_b, m_b = twin.fault_steps([fb, fd])
    assert u_b == 10
    assert m_b == 14


# ---------------------------------------------------------------------------
# 4. Twin warm-up repair & pools
# ---------------------------------------------------------------------------


def test_warmup_pool_independence_and_mutation() -> None:
    """warmup_pool and transient_pool are distinct objects and mutating one does not mutate the other."""
    rec = twin.run_episode(777, None)
    strat = rec["strat"]

    assert strat["warmup_pool"] is not strat["transient_pool"]
    assert strat["warmup_pool"] == strat["transient_pool"]

    original_val = strat["transient_pool"][0][0]
    strat["warmup_pool"][0][0] = 999999.0
    assert strat["transient_pool"][0][0] == original_val
    assert strat["transient_pool"][0][0] != 999999.0


def test_warmup_key_renames_and_absence_of_old_keys() -> None:
    """Renamed keys has_warmup_period and is_warmup_episode are True; old keys are absent."""
    rec = twin.run_episode(777, None)
    strat = rec["strat"]

    assert strat["has_warmup_period"] is True
    assert strat["is_warmup_episode"] is True
    assert "warmup_flag" not in strat
    assert "is_warmup" not in strat


def test_transient_channels_present_with_15_steps() -> None:
    """All 5 transient channels are present with exactly 15 steps per machine/buffer."""
    rec = twin.run_episode(777, None)
    strat = rec["strat"]
    channels = strat["transient_channels"]

    required_channels = ["observations", "states", "buffers", "throughput", "currents"]
    for ch in required_channels:
        assert ch in channels, f"Missing transient channel: {ch}"
        rows = channels[ch]
        assert len(rows) > 0
        for row in rows:
            assert len(row) == config.WARMUP_STEPS  # 15


def test_masked_variant_strat_denominator_285_vs_300() -> None:
    """Variant strat state histograms use denominator 285 (T - WARMUP_STEPS) vs baseline 300 (T)."""
    rec_base = twin.run_episode(777, None)
    rec_var = twin.run_episode(777, None, variant=config.VARIANT_ID)

    base_strat = rec_base["strat"]
    var_strat = rec_var["strat"]

    # In baseline, Machine A1 has STARVED in warmup window (steps 0..14)
    # With denominator 300, STARVED is > 0
    # In variant, warmup is masked, so denominator is 285 and steps 0..14 are excluded
    assert base_strat["state_histograms"]["A1"]["STARVED"] > 0.0
    assert var_strat["state_histograms"]["A1"]["STARVED"] == 0.0
    assert var_strat["state_histograms"]["A1"]["RUN"] == 1.0

    # Check plant_state_rollup active machines total
    active_machines = var_strat["plant_state_rollup"]["machines"]
    assert len(active_machines) == 24


def test_stationarity_probe_records_without_gating() -> None:
    """probe_stationarity records starved share and buffer occupancy without gating or raising."""
    rec = twin.run_episode(777, None)
    probe = twin.probe_stationarity(rec)

    assert isinstance(probe, dict)
    for key in (
        "transient_starved_share",
        "post_starved_share",
        "starved_delta",
        "transient_buffer_mean",
        "post_buffer_mean",
        "buffer_delta",
        "transient_buffer_occupancy",
    ):
        assert key in probe
        assert isinstance(probe[key], float)

    # Empty record test does not gate or raise
    empty_probe = twin.probe_stationarity({})
    assert isinstance(empty_probe, dict)
    assert empty_probe["transient_starved_share"] == 0.0


# ---------------------------------------------------------------------------
# 5. Downstream graded severity
# ---------------------------------------------------------------------------


def test_downstream_graded_severity_distinguishes_variant_and_freezes_baseline() -> (
    None
):
    """Variant 1σ vs 7σ produces different kit_sev_max; baseline produces identical parts and no kit_sev_max."""
    f1 = {
        "id": "F-X",
        "class": "drift",
        "origin": "B2",
        "t0": 150,
        "dur": 12,
        "mag_sigma": 1.0,
    }
    f7 = {
        "id": "F-Y",
        "class": "drift",
        "origin": "B2",
        "t0": 150,
        "dur": 12,
        "mag_sigma": 7.0,
    }

    # Variant episodes distinguish severity downstream
    var1 = twin.run_episode(777, copy.deepcopy(f1), variant=config.VARIANT_ID)
    var7 = twin.run_episode(777, copy.deepcopy(f7), variant=config.VARIANT_ID)
    assert "kit_sev_max" in var1["strat"]
    assert "kit_sev_max" in var7["strat"]
    assert var1["strat"]["kit_sev_max"] != var7["strat"]["kit_sev_max"]
    assert var1["strat"]["kit_sev_max"] == 1.0
    assert var7["strat"]["kit_sev_max"] == 7.0

    # Baseline episodes do NOT carry kit_sev_max and produce identical parts
    base1 = twin.run_episode(777, copy.deepcopy(f1))
    base7 = twin.run_episode(777, copy.deepcopy(f7))
    assert "kit_sev_max" not in base1["strat"]
    assert "kit_sev_max" not in base7["strat"]
    assert base1["parts"] == base7["parts"]


# ---------------------------------------------------------------------------
# 6. Mag bounds & adversarial cases
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad_mag", [100, 0.01, -3, 8.1, 0.49, True, "abc"])
def test_validate_mag_sigma_out_of_range_raises(bad_mag: object) -> None:
    """Out-of-range or invalid mag_sigma raises ValueError in _validate."""
    fault = {
        "origin": "B2",
        "class": "drift",
        "t0": 150,
        "dur": 12,
        "mag_sigma": bad_mag,
    }
    with pytest.raises(ValueError, match="mag_sigma out of range"):
        twin._validate(777, fault)


@pytest.mark.parametrize("valid_mag", [0.0, 0.5, 1.0, 3.0, 4.0, 7.0, 8.0])
def test_validate_mag_sigma_valid_bounds_pass(valid_mag: float) -> None:
    """Valid boundary and representative mag_sigma values pass _validate."""
    fault = {
        "origin": "B2",
        "class": "drift",
        "t0": 150,
        "dur": 12,
        "mag_sigma": valid_mag,
    }
    norm = twin._validate(777, fault)
    assert len(norm) == 1
    assert norm[0]["mag_sigma"] == valid_mag


# ---------------------------------------------------------------------------
# 7. Evidence provenance and dataset filter contract
# ---------------------------------------------------------------------------


def test_assert_warmup_excluded_contract() -> None:
    """assert_warmup_excluded passes on step >= 15 and raises on unfiltered dataframe."""
    df_raw = pd.DataFrame(
        {
            "step": list(range(30)),
            "warmup_flag": [True] * 15 + [False] * 15,
            "val": [1.0] * 30,
        }
    )

    # Unfiltered dataframe raises
    with pytest.raises(ValueError, match="Warm-up contract violation"):
        dataset_export.assert_warmup_excluded(df_raw)

    # Filtered dataframe passes
    df_clean = df_raw[df_raw["step"] >= config.WARMUP_STEPS].copy()
    df_clean["warmup_flag"] = False
    dataset_export.assert_warmup_excluded(df_clean)


def test_calibration_warmup_steps_excluded(tmp_path: pathlib.Path) -> None:
    """Calibration pile excludes warm-up window (CAL_WIN - WARMUP_STEPS = 105 rows, steps >= 15)."""
    out_parquet = tmp_path / "cal.parquet"
    calibrate.calibrate(seeds=[7], out=out_parquet)
    df, _ = calibrate.load_calibration(out_parquet)
    assert len(df) == config.CAL_WIN - config.WARMUP_STEPS  # 105
    if "step" in df.columns:
        assert (df["step"] >= config.WARMUP_STEPS).all()


def test_export_evidence_provenance_manifest(tmp_path: pathlib.Path) -> None:
    """export_evidence with exclude_warmup=True records exclude_warmup=True and warmup_steps=15 in manifest.json."""
    evidence.export_evidence(out_dir=str(tmp_path), seeds=[7], exclude_warmup=True)
    manifest_path = tmp_path / "manifest.json"
    assert manifest_path.exists()

    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)

    assert manifest["exclude_warmup"] is True
    assert manifest["warmup_steps"] == config.WARMUP_STEPS
    assert len(manifest["windows"]) > 0
    for w in manifest["windows"]:
        assert w["exclude_warmup"] is True
        assert w["warmup_steps"] == config.WARMUP_STEPS


def test_export_evidence_false_branch_warns(tmp_path: pathlib.Path) -> None:
    """export_evidence with exclude_warmup=False issues a warning and records False in manifest."""
    with pytest.warns(UserWarning, match="exclude_warmup=False"):
        evidence.export_evidence(out_dir=str(tmp_path), seeds=[7], exclude_warmup=False)

    manifest_path = tmp_path / "manifest.json"
    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)

    assert manifest["exclude_warmup"] is False
    assert manifest["warmup_steps"] == config.WARMUP_STEPS


# ---------------------------------------------------------------------------
# 8. Non-vacuity probes
# ---------------------------------------------------------------------------


def test_non_vacuity_share_threshold_99_percent_fails() -> None:
    """Non-vacuity probe: demanding 99% incipient share fails loudly."""
    rows = twin.build_faults_variant(12345)
    non_rep = [r for r in rows if not r.get("rep")]
    incip = [r for r in non_rep if r["mag_rung"] == "incipient"]
    assert not (len(incip) / len(non_rep) >= 0.99)


def test_non_vacuity_budget_pass_on_15_steps_raises() -> None:
    """Non-vacuity probe: 15-step drift cannot pass check_rate_budget."""
    specs = [{"origin": "B2", "class": "drift", "t0": 150, "dur": 15}]
    with pytest.raises(ValueError):
        twin.check_rate_budget(specs, scored=180)


def test_non_vacuity_pool_independence_is_check_fails() -> None:
    """Non-vacuity probe: warmup_pool and transient_pool must not be identical objects."""
    rec = twin.run_episode(777, None)
    strat = rec["strat"]
    assert not (strat["warmup_pool"] is strat["transient_pool"])
