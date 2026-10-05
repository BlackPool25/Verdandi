"""Contract tests for Dataset schema v5 (M0.2f Trainable Rework).

Requirements:
- schema_version == 5
- Per-step labels present: y, fault_mask, fault_family, fault_mode, is_warmup, shf_flag, is_down, root_id_step, hop_step
- Split-head features present:
  H-state: dwell_steps, cycle_lag, stale_hold_run, down_run, buffer_occ, state_hist_delta
  H-part: degrade_flag_count, reject_flag_count, rwk_passes, funnel_delta
- Hardened writer options: sorted columns, snappy compression, 2.6 parquet version
- Flag-day reader: load_v4_dataset rejects v5 loudly; load_v5_dataset accepts v5
- NO scaler.pkl
"""

from __future__ import annotations

import pytest

from src import config, dataset_export

pytestmark = [pytest.mark.k1, pytest.mark.battery]

V5_REQUIRED_LABEL_COLS = {
    "y",
    "fault_mask",
    "fault_family",
    "fault_mode",
    "is_warmup",
    "shf_flag",
    "is_down",
    "root_id_step",
    "hop_step",
}

V5_REQUIRED_STATE_HEAD_COLS = {
    "dwell_steps",
    "cycle_lag",
    "stale_hold_run",
    "down_run",
    "buffer_occ",
    "state_hist_delta",
}

V5_REQUIRED_PART_HEAD_COLS = {
    "degrade_flag_count",
    "reject_flag_count",
    "rwk_passes",
    "funnel_delta",
}


class TestDatasetV5Contract:
    def test_schema_version_is_5(self):
        assert config.TWIN_SCHEMA == 5

    def test_v5_export_columns_and_contract(self, tmp_path):
        out_parquet = tmp_path / "dataset_v5.parquet"
        res = dataset_export.export_contract_dataset_v5(
            out_dir=tmp_path, seeds=[7, 11, 13, 42]
        )
        assert out_parquet.exists()
        df = dataset_export.load_v5_dataset(res["out"])

        # Check all required label columns
        assert V5_REQUIRED_LABEL_COLS.issubset(set(df.columns)), (
            f"Missing label cols: {V5_REQUIRED_LABEL_COLS - set(df.columns)}"
        )

        # Check all required H-state head columns
        assert V5_REQUIRED_STATE_HEAD_COLS.issubset(set(df.columns)), (
            f"Missing H-state cols: {V5_REQUIRED_STATE_HEAD_COLS - set(df.columns)}"
        )

        # Check all required H-part head columns
        assert V5_REQUIRED_PART_HEAD_COLS.issubset(set(df.columns)), (
            f"Missing H-part cols: {V5_REQUIRED_PART_HEAD_COLS - set(df.columns)}"
        )

        # Determinism: columns must be alphabetically sorted
        assert list(df.columns) == sorted(df.columns)

        # Check schema_version column values
        assert (df["schema_version"] == 5).all()

        # Check no scaler.pkl
        assert not (tmp_path / "scaler.pkl").exists()

    def test_v4_reader_rejects_v5(self, tmp_path):
        res = dataset_export.export_contract_dataset_v5(out_dir=tmp_path, seeds=[7, 11])
        with pytest.raises(ValueError, match="v4 reader rejects non-v4 dataset"):
            dataset_export.load_v4_dataset(res["out"])

    def test_window_config_v5_fields(self, tmp_path):
        dataset_export.export_contract_dataset_v5(out_dir=tmp_path, seeds=[7, 11])
        cfg_path = tmp_path / "window_config.json"
        assert cfg_path.exists()

        import json

        with open(cfg_path) as f:
            cfg = json.load(f)

        assert cfg["schema_version"] == 5
        assert cfg["B_i"] is None
        assert cfg["scale_status"] == "unresolved"
        assert cfg["scale_cover"] == "dyadic-1..64"
        assert cfg["envelope_definition_id"] == "GES2N-v1"
