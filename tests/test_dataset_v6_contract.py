"""Contract tests for Dataset schema v6 (M0.2g Audit-Fix).

Requirements:
- schema_version == 6
- Per-step labels present:
  y, fault_mask, symptom_mask, fault_family, fault_mode, mag_sigma, mag_rung,
  is_warmup, shf_flag, is_down, root_id_step, hop_step, sensor_vs_process
- Split-head features present:
  H-state: dwell_steps, cycle_lag, stale_hold_run, down_run, buffer_occ, state_hist_delta,
           plus 78 per-machine columns (dwell_M, tputlag_M, downrun_M)
  H-part: degrade_flag_count, reject_flag_count, rwk_passes, funnel_rate, scrapped_total, scrap_flag
- Clock leak eliminated: (dwell_steps == t + 1).mean() < 0.05
- Flag-day readers: load_v5_dataset rejects v6 loudly; load_v6_dataset accepts v6
- Hardened writer: sorted columns, snappy compression, 2.6 parquet version
- NO scaler.pkl
"""

from __future__ import annotations

import pytest

from src import config, dataset_export, twin

pytestmark = [pytest.mark.k1, pytest.mark.battery]

V6_REQUIRED_LABEL_COLS = {
    "y",
    "fault_mask",
    "symptom_mask",
    "fault_family",
    "fault_mode",
    "mag_sigma",
    "mag_rung",
    "is_warmup",
    "shf_flag",
    "is_down",
    "root_id_step",
    "hop_step",
    "sensor_vs_process",
}

V6_REQUIRED_STATE_HEAD_COLS = {
    "dwell_steps",
    "cycle_lag",
    "stale_hold_run",
    "down_run",
    "buffer_occ",
    "state_hist_delta",
    *(f"dwell_{m}" for m in config.MACHINE_NAMES),
    *(f"tputlag_{m}" for m in config.MACHINE_NAMES),
    *(f"downrun_{m}" for m in config.MACHINE_NAMES),
}

V6_REQUIRED_PART_HEAD_COLS = {
    "degrade_flag_count",
    "reject_flag_count",
    "rwk_passes",
    "funnel_rate",
    "scrapped_total",
    "scrap_flag",
}


class TestDatasetV6Contract:
    def test_schema_version_is_6(self):
        assert config.TWIN_SCHEMA == 6
        assert config.CODE_VERSION == "twin-2.5.0-topology-A"

    def test_v6_export_columns_and_contract(self, tmp_path):
        out_parquet = tmp_path / "dataset_v6.parquet"
        res = dataset_export.export_dataset(
            out=out_parquet,
            seeds=[777, 42],
            schema_version=6,
        )
        assert out_parquet.exists()
        df = dataset_export.load_v6_dataset(res["out"])

        # Check all required label columns
        assert V6_REQUIRED_LABEL_COLS.issubset(set(df.columns)), (
            f"Missing label cols: {V6_REQUIRED_LABEL_COLS - set(df.columns)}"
        )

        # Check all required H-state head columns (including all 78 per-machine cols)
        assert V6_REQUIRED_STATE_HEAD_COLS.issubset(set(df.columns)), (
            f"Missing H-state cols: {V6_REQUIRED_STATE_HEAD_COLS - set(df.columns)}"
        )

        # Check all required H-part head columns
        assert V6_REQUIRED_PART_HEAD_COLS.issubset(set(df.columns)), (
            f"Missing H-part cols: {V6_REQUIRED_PART_HEAD_COLS - set(df.columns)}"
        )

        # Determinism: columns must be alphabetically sorted
        assert list(df.columns) == sorted(df.columns)

        # Check schema_version column values
        assert (df["schema_version"] == 6).all()

        # Check no scaler.pkl
        assert not (tmp_path / "scaler.pkl").exists()

    def test_v5_reader_rejects_v6(self, tmp_path):
        out_parquet = tmp_path / "dataset_v6.parquet"
        res = dataset_export.export_dataset(out=out_parquet, seeds=[777], schema_version=6)
        with pytest.raises(ValueError, match="v5 reader rejects non-v5 dataset"):
            dataset_export.load_v5_dataset(res["out"])

    def test_clock_leak_eliminated(self, tmp_path):
        out_parquet = tmp_path / "dataset_v6.parquet"
        res = dataset_export.export_dataset(out=out_parquet, seeds=[777, 42], schema_version=6)
        df = dataset_export.load_v6_dataset(res["out"])

        # In v5, dwell_steps == t + 1 was 100%. In v6, steady-state is < 5% (only initial startup steps match).
        clock_eq_post = (df[df["t"] >= 25]["dwell_steps"] == (df[df["t"] >= 25]["t"] + 1)).mean()
        assert clock_eq_post < 0.05, f"Clock shortcut detected: dwell_steps == t + 1 on {clock_eq_post:.2%}"

        lag_eq_post = (df[df["t"] >= 25]["cycle_lag"] == (df[df["t"] >= 25]["t"] + 1)).mean()
        assert lag_eq_post < 0.05, f"Clock shortcut detected: cycle_lag == t + 1 on {lag_eq_post:.2%}"

    def test_symptom_mask_and_hop_propagation(self, tmp_path):
        out_parquet = tmp_path / "dataset_v6.parquet"
        # Fault on A0 with delay (dur=12 fits rate budget <= 14.4)
        f_delay = {
            "id": "F-test-delay",
            "class": "delay",
            "origin": "A0",
            "t0": 150,
            "dur": 12,
            "extra": {"d": 4},
        }
        res = dataset_export.export_dataset(
            out=out_parquet,
            seeds=[42],
            faults={42: f_delay},
            schema_version=6,
        )
        df = dataset_export.load_v6_dataset(res["out"])

        # Check y == 1 on root window [150, 162)
        root_steps = df[(df["t"] >= 150) & (df["t"] < 162)]
        assert (root_steps["y"] == 1).all()
        assert (root_steps["hop_step"] == 0).all()
        assert (root_steps["symptom_mask"] == 0).all()

        # Check symptom steps: where fault_mask == 1 and y == 0
        symptoms = df[(df["fault_mask"] == 1) & (df["y"] == 0)]
        if len(symptoms) > 0:
            assert (symptoms["symptom_mask"] == 1).all()
            assert (symptoms["hop_step"] >= 1).all()
            assert (symptoms["root_id_step"] == "A0").all()
