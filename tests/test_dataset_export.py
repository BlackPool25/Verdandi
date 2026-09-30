"""Tests for src/dataset_export.py (Todo 5).

Covers:
1. Deterministic Parquet export with sorted column keys.
2. window_config.json with owned fields, CAL_WIN=120, T=300, schema_version=3.
3. Ingestion metadata (hash, code_version, schema_version=3, seeds, funnel summary).
4. Absolute rule: ZERO scaler.pkl fitted or written.
5. 5x same-seed export produces bit-identical hashes for Parquet and metadata.
6. Size cap check.
7. Backward compatibility: v2 reader function loudly raises ValueError mentioning v3.
"""

import hashlib
import json
import pathlib

import pytest

from src import config, dataset_export


def test_export_single_seed_happy_path(tmp_path):
    out_parquet = tmp_path / "artifacts" / "dataset_v3.parquet"
    res = dataset_export.export(seed=777, out=out_parquet)

    assert out_parquet.exists()
    assert res["row_count"] == 300
    assert res["dataset_hash"]

    # Verify sorted column keys
    df = dataset_export.load_dataset(out_parquet)
    assert list(df.columns) == sorted(df.columns)
    assert df["schema_version"].iloc[0] == 3
    assert df["code_version"].iloc[0] == config.CODE_VERSION
    assert df["episode_id"].iloc[0] == 777

    # Stratification keys presence
    for key in dataset_export.OWNED_STRAT_FIELDS:
        assert key in df.columns, f"Missing owned stratification key: {key}"

    # Verify window_config.json
    win_cfg_path = tmp_path / "artifacts" / "window_config.json"
    assert win_cfg_path.exists()
    win_cfg = json.loads(win_cfg_path.read_text())
    assert win_cfg["schema_version"] == 3
    assert win_cfg["code_version"] == config.CODE_VERSION
    assert win_cfg["cal_win"] == 120
    assert win_cfg["T"] == 300
    assert win_cfg["warmup_steps"] == 15
    assert set(win_cfg["owned_fields"]) == set(dataset_export.OWNED_STRAT_FIELDS)

    # Verify metadata.json & ingestion_metadata.json
    for meta_name in ("metadata.json", "ingestion_metadata.json"):
        meta_path = tmp_path / "artifacts" / meta_name
        assert meta_path.exists()
        meta = json.loads(meta_path.read_text())
        assert meta["schema_version"] == 3
        assert meta["code_version"] == config.CODE_VERSION
        assert meta["dataset_hash"] == res["dataset_hash"]
        assert meta["seeds"] == [777]
        assert "funnel_summary" in meta
        assert "median_sunk" in meta["funnel_summary"]

    # ABSOLUTE RULE: NO scaler.pkl!
    scaler_file = tmp_path / "artifacts" / "scaler.pkl"
    assert not scaler_file.exists(), "LEAKAGE VIOLATION: scaler.pkl must NOT be created"


def test_export_5x_same_seed_bit_identical(tmp_path):
    """5x same-seed export must produce byte-identical Parquet files and metadata."""
    hashes_parquet = []
    hashes_meta = []

    for i in range(5):
        run_file = tmp_path / f"test_run_{i}.parquet"
        _ = dataset_export.export(seed=777, out=run_file)
        with open(run_file, "rb") as f:
            hashes_parquet.append(hashlib.sha256(f.read()).hexdigest())

        meta_path = tmp_path / "metadata.json"
        with open(meta_path, "rb") as f:
            hashes_meta.append(hashlib.sha256(f.read()).hexdigest())

    assert len(set(hashes_parquet)) == 1, (
        f"Non-deterministic Parquet hashes across 5 runs: {hashes_parquet}"
    )
    assert len(set(hashes_meta)) == 1, (
        f"Non-deterministic metadata.json hashes across 5 runs: {hashes_meta}"
    )


def test_export_size_cap_check(tmp_path):
    """Size cap check must reject exports exceeding max_bytes."""
    out_file = tmp_path / "capped.parquet"
    with pytest.raises(ValueError, match="size cap violated"):
        dataset_export.export(seed=777, out=out_file, max_bytes=100)


def test_v2_reader_loudly_rejects_v3_records_and_dataset(tmp_path):
    """v2 reader function must loudly raise ValueError mentioning v3."""
    out_parquet = tmp_path / "dataset_v3.parquet"
    dataset_export.export(seed=777, out=out_parquet)

    # Direct dict rejection
    with pytest.raises(ValueError, match="v2 reader non-comparable.*v3"):
        dataset_export.load_v2_dataset({"schema_version": 3, "data": []})

    # Parquet file rejection
    with pytest.raises(ValueError, match="v2 reader non-comparable.*v3"):
        dataset_export.load_v2_dataset(out_parquet)


def test_absolute_rule_no_scaler_pkl_in_artifacts():
    """Ensure artifacts directory contains zero scaler.pkl."""
    artifacts_dir = pathlib.Path("artifacts")
    if artifacts_dir.exists():
        assert not (artifacts_dir / "scaler.pkl").exists()
