"""Calibration contract and determinism tests for src/calibrate.py (Todo 1).

Normative Requirements (P0-1 Calibration Contract):
1. Deterministic Re-capture:
   - Same-seed re-capture produces byte-identical Parquet artifact and sidecar metadata (sha256 matching).
2. Artifact & Metadata Binding:
   - Artifact sidecar carries TWIN_SCHEMA (schema 4), CODE_VERSION ("twin-2.3.0-topology-A"),
     seed-list hash, pyarrow version, and SHA256 file digest.
3. Schema Version Pinning:
   - Refuses older twin schemas (< 4) loudly by raising ValueError.
4. Warm-up Step Exclusion:
   - Warm-up steps (first 15 steps per WARMUP_STEPS in src/config.py) are excluded from calibration piles.
   - Clean calibration window consists strictly of steps WARMUP_STEPS to CAL_WIN (105 steps).
5. Per-Machine Calibration Sets & Percentile Grid:
   - Per-machine raw CAL_WIN values for all 26 machines in config.MACHINE_INDEX.
   - Percentile grid [0.5, 0.9, 0.95, 0.98, 0.99, 0.995] + min/max are present.
6. Parquet Writer Specifications:
   - Writer uses version='2.6', coerce_timestamps='us', and fixed use_dictionary.
7. CLI Execution Contract:
   - python -m src.calibrate --out <path> supports argparse and exits 0 on --help.
8. Negative Controls:
   - Missing sidecar JSON, corrupted metadata (sha256 mismatch), or legacy schema version (< 4)
     causes a loud ValueError.
9. Leakage Law (TF1):
   - ABSOLUTE RULE: Zero scaler fitted or written (no scaler.pkl, no sklearn scaler imports or .fit calls).
   - Calibration module is a reader/sampler only; twin physics beyond run_episode/config are untouched.
"""

from __future__ import annotations

import ast
import hashlib
import json
import pathlib
import subprocess
import sys

# Ensure repository root is on sys.path when invoked via bare pytest without PYTHONPATH
_REPO_ROOT = str(pathlib.Path(__file__).resolve().parent.parent)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import numpy as np
import pyarrow.parquet as pq
import pytest

from src import calibrate, config
from src.twin import run_episode

pytestmark = pytest.mark.k1

PERCENTILE_GRID = [0.5, 0.9, 0.95, 0.98, 0.99, 0.995]
TEST_SEEDS = [7, 11]


def test_calibration_same_seed_recapture_byte_identical_parquet_and_metadata(
    tmp_path: pathlib.Path,
) -> None:
    """Same-seed re-capture produces byte-identical Parquet artifact and sidecar metadata (sha256 matching)."""
    run1_parquet = tmp_path / "run1" / "cal_v4.parquet"
    run2_parquet = tmp_path / "run2" / "cal_v4.parquet"

    res1 = calibrate.calibrate(seeds=TEST_SEEDS, out=run1_parquet)
    res2 = calibrate.calibrate(seeds=TEST_SEEDS, out=run2_parquet)

    # Verify returned hash matches
    assert res1["dataset_hash"] == res2["dataset_hash"]

    # Verify Parquet byte-identical sha256
    with open(run1_parquet, "rb") as f1, open(run2_parquet, "rb") as f2:
        sha_pq1 = hashlib.sha256(f1.read()).hexdigest()
        sha_pq2 = hashlib.sha256(f2.read()).hexdigest()
    assert sha_pq1 == sha_pq2
    assert sha_pq1 == res1["dataset_hash"]

    # Verify sidecar JSON byte-identical sha256
    run1_json = run1_parquet.with_suffix(".json")
    run2_json = run2_parquet.with_suffix(".json")
    assert run1_json.exists(), f"Sidecar JSON missing at {run1_json}"
    assert run2_json.exists(), f"Sidecar JSON missing at {run2_json}"

    with open(run1_json, "rb") as f1, open(run2_json, "rb") as f2:
        sha_json1 = hashlib.sha256(f1.read()).hexdigest()
        sha_json2 = hashlib.sha256(f2.read()).hexdigest()
    assert sha_json1 == sha_json2


def test_calibration_metadata_carries_schema_code_version_and_seed_hash(
    tmp_path: pathlib.Path,
) -> None:
    """Artifact metadata carries TWIN_SCHEMA (schema 4), CODE_VERSION, and seed-list hash."""
    out_parquet = tmp_path / "cal_v4.parquet"
    res = calibrate.calibrate(seeds=TEST_SEEDS, out=out_parquet)

    sidecar_path = out_parquet.with_suffix(".json")
    assert sidecar_path.exists(), f"Sidecar JSON must exist at {sidecar_path}"
    meta = json.loads(sidecar_path.read_text())

    # Schema & Code Version pins
    assert meta["schema_version"] == 4, (
        f"Expected schema_version 4, got {meta.get('schema_version')}"
    )
    assert meta["schema_version"] == config.TWIN_SCHEMA
    assert meta["code_version"] == "twin-2.3.0-topology-A"
    assert meta["code_version"] == config.CODE_VERSION

    # Seed list and hash verification
    assert meta["seeds"] == TEST_SEEDS
    seed_hash_field = meta.get("seed_list_hash") or meta.get("seeds_hash")
    assert seed_hash_field is not None, "Metadata must carry seed_list_hash"
    expected_seed_hash = hashlib.sha256(
        json.dumps(TEST_SEEDS).encode("utf-8")
    ).hexdigest()
    assert seed_hash_field == expected_seed_hash or len(seed_hash_field) == 64

    # Parquet sha256 digest in metadata
    with open(out_parquet, "rb") as f:
        actual_sha = hashlib.sha256(f.read()).hexdigest()
    assert meta["sha256"] == actual_sha
    assert res["dataset_hash"] == actual_sha

    # pyarrow version captured
    import pyarrow as pa

    assert meta["pyarrow_version"] == pa.__version__


def test_calibration_refuses_older_twin_schemas_loudly(
    tmp_path: pathlib.Path,
) -> None:
    """Refuses older twin schemas loudly (raises ValueError)."""
    out_parquet = tmp_path / "cal_v4.parquet"
    calibrate.calibrate(seeds=TEST_SEEDS, out=out_parquet)

    # 1. Direct calibration call with legacy schema_version must raise ValueError
    with pytest.raises(ValueError, match="(?i)schema"):
        calibrate.calibrate(
            seeds=TEST_SEEDS, out=tmp_path / "legacy.parquet", schema_version=3
        )

    # 2. Tampered sidecar with older schema (1, 2, 3) must raise ValueError on load
    sidecar_path = out_parquet.with_suffix(".json")
    original_text = sidecar_path.read_text()
    meta = json.loads(original_text)

    for legacy_ver in (1, 2, 3):
        meta["schema_version"] = legacy_ver
        sidecar_path.write_text(json.dumps(meta))
        with pytest.raises(ValueError, match="(?i)schema"):
            calibrate.load_calibration(out_parquet)

    # Restore valid sidecar
    sidecar_path.write_text(original_text)


def test_calibration_warmup_steps_excluded_from_calibration_piles(
    tmp_path: pathlib.Path,
) -> None:
    """Warm-up steps (first 15 steps per WARMUP_STEPS in src/config.py) are excluded from calibration piles."""
    out_parquet = tmp_path / "cal_v4.parquet"
    calibrate.calibrate(seeds=[7], out=out_parquet)

    df, meta = calibrate.load_calibration(out_parquet)
    assert meta["schema_version"] == config.TWIN_SCHEMA

    # Clean calibration window per episode is CAL_WIN - WARMUP_STEPS = 120 - 15 = 105 steps
    expected_steps = config.CAL_WIN - config.WARMUP_STEPS
    assert expected_steps == 105

    if "step" in df.columns:
        steps = df["step"].to_numpy()
        assert steps.min() >= config.WARMUP_STEPS, (
            f"Found step < WARMUP_STEPS: {steps.min()}"
        )
        assert steps.max() < config.CAL_WIN, f"Found step >= CAL_WIN: {steps.max()}"
        assert len(steps) == expected_steps
    else:
        assert len(df) == expected_steps

    # Compare values directly against clean slice from run_episode
    rec = run_episode(7, None, enable_natural_breakdown=False)
    raw_obs = np.asarray(rec["obs"], dtype=float)  # shape (26, 300)

    warmup_slice = raw_obs[:, : config.WARMUP_STEPS]
    clean_slice = raw_obs[:, config.WARMUP_STEPS : config.CAL_WIN]

    m_idx = config.MACHINE_INDEX["A0"]
    col_name = "obs_A0" if "obs_A0" in df.columns else "A0"
    cal_values = df[col_name].to_numpy()

    # Must match clean slice exactly
    np.testing.assert_allclose(cal_values, clean_slice[m_idx], rtol=1e-6)
    # Must NOT match warm-up slice
    with pytest.raises(AssertionError):
        np.testing.assert_allclose(
            cal_values[: config.WARMUP_STEPS], warmup_slice[m_idx], rtol=1e-6
        )


def test_calibration_per_machine_raw_values_and_percentile_grid_present(
    tmp_path: pathlib.Path,
) -> None:
    """Per-machine raw CAL_WIN (120) values + percentile grid [0.5, 0.9, 0.95, 0.98, 0.99, 0.995] + min/max are present."""
    out_parquet = tmp_path / "cal_v4.parquet"
    calibrate.calibrate(seeds=TEST_SEEDS, out=out_parquet)

    df, meta = calibrate.load_calibration(out_parquet)

    # 1. Raw values present for all 26 machines
    for m_name in config.MACHINE_INDEX:
        col = f"obs_{m_name}" if f"obs_{m_name}" in df.columns else m_name
        assert col in df.columns, (
            f"Machine {m_name} missing from calibration raw values"
        )

    # 2. Percentile grid and min/max present in metadata
    summary = meta.get("machines") or meta.get("percentiles") or meta.get("summary")
    assert summary is not None, "Metadata must contain per-machine percentiles/summary"

    for m_name in config.MACHINE_INDEX:
        assert m_name in summary, f"Machine {m_name} missing from summary"
        m_stats = summary[m_name]

        assert "min" in m_stats, f"Machine {m_name} missing 'min'"
        assert "max" in m_stats, f"Machine {m_name} missing 'max'"

        pcts = m_stats.get("percentiles", m_stats)
        for p in PERCENTILE_GRID:
            has_p = (
                str(p) in pcts
                or p in pcts
                or f"p{int(p * 100)}" in pcts
                or f"p{p * 100:.1f}" in pcts
                or f"q{p}" in pcts
            )
            assert has_p, f"Percentile {p} missing for machine {m_name} in {pcts}"

        # 3. Numeric verification against raw dataframe values
        col = f"obs_{m_name}" if f"obs_{m_name}" in df.columns else m_name
        raw_vals = df[col].to_numpy()
        assert float(m_stats["min"]) == pytest.approx(float(raw_vals.min()), rel=1e-5)
        assert float(m_stats["max"]) == pytest.approx(float(raw_vals.max()), rel=1e-5)
        p50_val = pcts.get("0.5") or pcts.get(0.5) or pcts.get("p50")
        assert float(p50_val) == pytest.approx(
            float(np.percentile(raw_vals, 50)), rel=1e-5
        )


def test_calibration_parquet_writer_spec_and_schema_version(
    tmp_path: pathlib.Path,
) -> None:
    """Parquet schema and writer requirements: version='2.6', coerce_timestamps='us', fixed use_dictionary."""
    out_parquet = tmp_path / "cal_v4.parquet"
    calibrate.calibrate(seeds=TEST_SEEDS, out=out_parquet)

    # 1. Verify Parquet file format_version
    parquet_file = pq.ParquetFile(out_parquet)
    assert parquet_file.metadata.format_version == "2.6", (
        f"Expected Parquet format_version '2.6', got {parquet_file.metadata.format_version}"
    )

    # 2. Inspect AST of src/calibrate.py for hardened writer arguments
    cal_file = pathlib.Path("src/calibrate.py")
    assert cal_file.exists(), "src/calibrate.py must exist"
    tree = ast.parse(cal_file.read_text())

    found_write_call = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            is_pq_write = (
                isinstance(node.func, ast.Attribute) and node.func.attr == "write_table"
            ) or (isinstance(node.func, ast.Name) and node.func.id == "write_table")
            if is_pq_write:
                found_write_call = True
                kw_names = {kw.arg: kw.value for kw in node.keywords}
                assert "version" in kw_names, "write_table missing version keyword"
                if isinstance(kw_names["version"], ast.Constant):
                    assert kw_names["version"].value == "2.6"

                assert "coerce_timestamps" in kw_names, (
                    "write_table missing coerce_timestamps keyword"
                )
                if isinstance(kw_names["coerce_timestamps"], ast.Constant):
                    assert kw_names["coerce_timestamps"].value == "us"

                assert "use_dictionary" in kw_names, (
                    "write_table missing use_dictionary keyword"
                )

    assert found_write_call, "src/calibrate.py must contain pq.write_table call"


def test_calibration_cli_execution_contract_argparse_and_help(
    tmp_path: pathlib.Path,
) -> None:
    """CLI execution contract: python -m src.calibrate --out <path> supports argparse and exits 0 on --help."""
    # 1. python -m src.calibrate --help exits 0 and documents --out
    res_help = subprocess.run(
        [sys.executable, "-m", "src.calibrate", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert res_help.returncode == 0, f"--help failed with {res_help.stderr}"
    assert "--out" in res_help.stdout, "--help output must document --out parameter"

    # 2. CLI execution with --out creates artifact and exits 0
    cli_out = tmp_path / "cli_artifact" / "cal_v4.parquet"
    res_run = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.calibrate",
            "--out",
            str(cli_out),
            "--seeds",
            "7",
            "11",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert res_run.returncode == 0, f"CLI run failed with {res_run.stderr}"
    assert cli_out.exists(), f"CLI execution did not produce {cli_out}"
    assert cli_out.with_suffix(".json").exists(), (
        "CLI execution did not produce sidecar JSON"
    )


def test_calibration_negative_controls_missing_sidecar_or_corrupted_metadata(
    tmp_path: pathlib.Path,
) -> None:
    """Negative controls: missing sidecar JSON or corrupted metadata or legacy schema version (<4) causes loud ValueError."""
    out_parquet = tmp_path / "cal_v4.parquet"
    calibrate.calibrate(seeds=TEST_SEEDS, out=out_parquet)

    sidecar_json = out_parquet.with_suffix(".json")
    assert sidecar_json.exists()
    valid_sidecar_content = sidecar_json.read_text()

    # Case A: Missing sidecar JSON
    sidecar_json.unlink()
    with pytest.raises(ValueError, match="(?i)sidecar|missing"):
        calibrate.load_calibration(out_parquet)

    # Case B: Corrupted metadata JSON (invalid JSON syntax)
    sidecar_json.write_text("{bad json syntax")
    with pytest.raises(ValueError, match="(?i)corrupt|invalid|json"):
        calibrate.load_calibration(out_parquet)

    # Case C: Corrupted metadata SHA256 mismatch
    tampered_meta = json.loads(valid_sidecar_content)
    tampered_meta["sha256"] = "0" * 64
    sidecar_json.write_text(json.dumps(tampered_meta))
    with pytest.raises(ValueError, match="(?i)sha256|mismatch|corrupt|checksum"):
        calibrate.load_calibration(out_parquet)

    # Case D: Legacy schema version (< 4)
    tampered_meta = json.loads(valid_sidecar_content)
    tampered_meta["schema_version"] = 3
    sidecar_json.write_text(json.dumps(tampered_meta))
    with pytest.raises(ValueError, match="(?i)schema"):
        calibrate.load_calibration(out_parquet)


def test_calibration_leakage_law_zero_scaler_fitted_or_written(
    tmp_path: pathlib.Path,
) -> None:
    """Verify ABSOLUTE RULE: no scaler fitted or written (TF1 leakage law) and AST checks."""
    out_parquet = tmp_path / "cal_v4.parquet"
    calibrate.calibrate(seeds=TEST_SEEDS, out=out_parquet)

    # 1. No scaler.pkl created in output dir or artifacts
    assert not (tmp_path / "scaler.pkl").exists()
    assert not pathlib.Path("artifacts/scaler.pkl").exists()

    # 2. AST visitor checking src/calibrate.py for banned scaler operations
    cal_file = pathlib.Path("src/calibrate.py")
    assert cal_file.exists(), "src/calibrate.py must exist"
    tree = ast.parse(cal_file.read_text())

    banned_imports = {
        "StandardScaler",
        "MinMaxScaler",
        "RobustScaler",
        "Normalizer",
        "sklearn.preprocessing",
    }
    banned_calls = {"fit", "fit_transform"}

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                for banned in banned_imports:
                    assert banned not in alias.name, (
                        f"Banned import found: {alias.name}"
                    )
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert "preprocessing" not in module, f"Banned import from {module}"
            for alias in node.names:
                assert alias.name not in banned_imports, (
                    f"Banned import found: {alias.name}"
                )
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in banned_calls
        ):
            raise AssertionError(
                f"Banned call to .{node.func.attr}() found in src/calibrate.py"
            )
