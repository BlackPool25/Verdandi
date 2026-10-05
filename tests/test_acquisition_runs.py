"""Verification suite for data acquisition timing/RSS vectors, run log, and check_gates CLI.

Normative requirements:
1. Run Vector Emission:
   - calibrate, evidence, and dataset_v4 runs emit properly structured JSONL rows to runs.jsonl.
   - Each row contains: run_id, job_name, wall_seconds, peak_rss_kb, peak_rss_mb,
     timestamp, status ("success" | "error"), artifact_path, schema_version, code_version.
2. Atomic & Concurrent Append:
   - Concurrent workers appending to runs.jsonl do not interleave, corrupt, or drop lines (POSIX flock).
3. Check Gates Verification:
   - check_gates.py --runs-log <path> verifies emitted vectors against export budget and budget factor.
   - Negative controls verify failure on error status, timing budget breach, or corrupted log.
4. Absolute Rule (Timing Assertions In Pytest):
   - Precedent: tests/test_twin_w6_determinism_wall.py:7-9.
   - Must NOT assert wall timing threshold bounds inside pytest (noise-dominated on shared runners).
   - Only assert numeric sanity (e.g. wall_seconds > 0, peak_rss > 0, isinstance float).
"""

from __future__ import annotations

import concurrent.futures
import json
import os
import pathlib
import subprocess
import sys
from datetime import datetime
from typing import Any

# Ensure repository root is on sys.path
_REPO_ROOT = str(pathlib.Path(__file__).resolve().parent.parent)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import pytest

from scripts import check_gates
from src import calibrate, dataset_export, evidence
from src.calibrate import append_run_vector, make_run_vector

pytestmark = pytest.mark.k1


def _worker_append(args: tuple[str, dict[str, Any]]) -> None:
    """Worker function for concurrent append test."""
    path_str, vector = args
    append_run_vector(path_str, vector)


def test_calibrate_run_vector_emission_library_and_cli(tmp_path: pathlib.Path) -> None:
    """Calibrate emits properly structured run vector to runs.jsonl via both library and CLI."""
    runs_log = tmp_path / "runs.jsonl"
    cal_out = tmp_path / "cal_v4.parquet"
    cli_out = tmp_path / "cal_cli.parquet"

    # 1. Python library invocation
    res = calibrate.calibrate(seeds=[7], out=cal_out, runs_log=runs_log)
    assert "run_vector" in res
    assert res["wall_seconds"] > 0
    assert res["peak_rss_kb"] > 0

    # 2. CLI invocation
    cmd = [
        sys.executable,
        "-m",
        "src.calibrate",
        "--out",
        str(cli_out),
        "--seeds",
        "7",
        "--runs-log",
        str(runs_log),
    ]
    subprocess.run(cmd, check=True)

    # 3. Verify lines in runs_log
    assert runs_log.exists()
    lines = [
        line.strip()
        for line in runs_log.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(lines) == 2

    for line in lines:
        data = json.loads(line)
        assert data["job_name"] == "calibrate"
        assert data["status"] == "success"
        # Numeric sanity only (ABSOLUTE RULE: no timing threshold bound asserts)
        assert isinstance(data["wall_seconds"], (int, float))
        assert data["wall_seconds"] > 0
        assert isinstance(data["peak_rss_kb"], (int, float))
        assert data["peak_rss_kb"] > 0
        assert isinstance(data["peak_rss_mb"], (int, float))
        assert data["peak_rss_mb"] > 0
        assert data["schema_version"] in (4, 5)
        assert len(data["run_id"]) > 0
        # Valid ISO timestamp
        dt = datetime.fromisoformat(data["timestamp"])
        assert dt is not None
        assert os.path.exists(data["artifact_path"])


def test_evidence_run_vector_emission_library_and_cli(tmp_path: pathlib.Path) -> None:
    """Evidence export emits properly structured run vector to runs.jsonl via library and CLI."""
    runs_log = tmp_path / "runs.jsonl"
    ev_out = tmp_path / "evidence_lib"
    cli_out = tmp_path / "evidence_cli"

    # 1. Python library invocation (single partition, 4 seeds for fast testing)
    res = evidence.export_evidence(
        out_dir=ev_out,
        partition="cell",
        seeds=[7, 11, 13, 42],
        runs_log=runs_log,
    )
    assert "run_vector" in res
    assert res["wall_seconds"] > 0
    assert res["peak_rss_kb"] > 0

    # 2. CLI invocation
    cmd = [
        sys.executable,
        "-m",
        "src.evidence",
        "--out",
        str(cli_out),
        "--partition",
        "cell",
        "--runs-log",
        str(runs_log),
    ]
    subprocess.run(cmd, check=True)

    # 3. Verify lines in runs_log
    assert runs_log.exists()
    lines = [
        line.strip()
        for line in runs_log.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(lines) == 2

    for line in lines:
        data = json.loads(line)
        assert data["job_name"] == "evidence"
        assert data["status"] == "success"
        assert isinstance(data["wall_seconds"], (int, float))
        assert data["wall_seconds"] > 0
        assert isinstance(data["peak_rss_kb"], (int, float))
        assert data["peak_rss_kb"] > 0
        assert isinstance(data["peak_rss_mb"], (int, float))
        assert data["peak_rss_mb"] > 0
        assert len(data["run_id"]) > 0
        dt = datetime.fromisoformat(data["timestamp"])
        assert dt is not None
        assert os.path.exists(data["artifact_path"])


def test_dataset_v4_run_vector_emission_library_and_cli(tmp_path: pathlib.Path) -> None:
    """Dataset v4 export emits properly structured run vector via library and CLI."""
    runs_log = tmp_path / "runs.jsonl"
    ds_out = tmp_path / "dataset_v4.parquet"
    cli_out = tmp_path / "ds_cli.parquet"

    # 1. Python library invocation
    res = dataset_export.export_v4(seeds=[7], out=ds_out, runs_log=runs_log)
    assert "run_vector" in res
    assert res["wall_seconds"] > 0
    assert res["peak_rss_kb"] > 0

    # 2. CLI invocation
    cmd = [
        sys.executable,
        "-m",
        "src.dataset_export",
        "--v4",
        "--out",
        str(cli_out),
        "--seed",
        "7",
        "--runs-log",
        str(runs_log),
    ]
    subprocess.run(cmd, check=True)

    # 3. Verify lines in runs_log
    assert runs_log.exists()
    lines = [
        line.strip()
        for line in runs_log.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(lines) == 2

    for line in lines:
        data = json.loads(line)
        assert data["job_name"] == "dataset_v4"
        assert data["status"] == "success"
        assert isinstance(data["wall_seconds"], (int, float))
        assert data["wall_seconds"] > 0
        assert isinstance(data["peak_rss_kb"], (int, float))
        assert data["peak_rss_kb"] > 0
        assert isinstance(data["peak_rss_mb"], (int, float))
        assert data["peak_rss_mb"] > 0
        assert data["schema_version"] == 4
        assert len(data["run_id"]) > 0
        dt = datetime.fromisoformat(data["timestamp"])
        assert dt is not None
        assert os.path.exists(data["artifact_path"])


def test_atomic_append_concurrent_workers(tmp_path: pathlib.Path) -> None:
    """Concurrent worker processes appending to runs.jsonl do not corrupt or interleave lines."""
    runs_log = tmp_path / "concurrent_runs.jsonl"
    num_entries = 40

    tasks: list[tuple[str, dict[str, Any]]] = []
    for i in range(num_entries):
        vec = make_run_vector(
            run_id=f"worker-test-{i:03d}",
            job_name="calibrate",
            wall_seconds=0.100 + (i * 0.001),
            peak_rss_kb=102400.0,
            status="success",
            artifact_path=f"artifacts/cal_{i}.parquet",
        )
        tasks.append((str(runs_log), vec))

    # Concurrently write from multiple processes
    with concurrent.futures.ProcessPoolExecutor(max_workers=8) as executor:
        list(executor.map(_worker_append, tasks))

    # Verify that exactly num_entries valid JSON lines were written without corruption
    assert runs_log.exists()
    raw_lines = runs_log.read_text(encoding="utf-8").splitlines()
    assert len(raw_lines) == num_entries

    parsed_ids = set()
    for line in raw_lines:
        record = json.loads(line)
        assert "run_id" in record
        parsed_ids.add(record["run_id"])

    assert len(parsed_ids) == num_entries
    assert parsed_ids == {f"worker-test-{i:03d}" for i in range(num_entries)}


def test_check_gates_runs_log_cli_success(tmp_path: pathlib.Path) -> None:
    """check_gates.py --runs-log verifies emitted vectors and passes on valid runs within budget."""
    runs_log = tmp_path / "runs.jsonl"

    # Emit three representative runs
    calibrate.calibrate(seeds=[7], out=tmp_path / "cal.parquet", runs_log=runs_log)
    evidence.export_evidence(
        out_dir=tmp_path / "ev",
        partition="cell",
        seeds=[7, 11, 13, 42],
        runs_log=runs_log,
    )
    dataset_export.export_v4(seeds=[7], out=tmp_path / "ds.parquet", runs_log=runs_log)

    # Invoke check_gates CLI
    cmd = [
        sys.executable,
        "scripts/check_gates.py",
        "--runs-log",
        str(runs_log),
        "--budget-factor",
        "1.02",
        "--export-budget",
        "60.0",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    assert proc.returncode == check_gates.EXIT_OK, (
        f"STDOUT: {proc.stdout}\nSTDERR: {proc.stderr}"
    )
    assert "PASS: all 3 run vectors verified within budget" in proc.stdout

    # Also verify Python API directly
    res = check_gates.run_runs_log_gate(
        str(runs_log), budget_factor=1.02, export_budget=60.0
    )
    assert res == check_gates.EXIT_OK


def test_check_gates_runs_log_negative_controls(tmp_path: pathlib.Path) -> None:
    """check_gates rejects runs log on error status, budget breach, or corrupted format."""
    # Negative Control 1: Status error
    err_log = tmp_path / "err_runs.jsonl"
    vec_err = make_run_vector(
        run_id="err-run-1",
        job_name="calibrate",
        wall_seconds=0.5,
        peak_rss_kb=100000.0,
        status="error",
        artifact_path="artifacts/cal_v4.parquet",
    )
    append_run_vector(err_log, vec_err)

    proc_err = subprocess.run(
        [sys.executable, "scripts/check_gates.py", "--runs-log", str(err_log)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc_err.returncode == check_gates.EXIT_ERROR
    assert "GATE FAILURE" in proc_err.stderr

    # Negative Control 2: Wall budget breach
    breach_log = tmp_path / "breach_runs.jsonl"
    vec_breach = make_run_vector(
        run_id="breach-run-1",
        job_name="dataset_v4",
        wall_seconds=50.0,
        peak_rss_kb=100000.0,
        status="success",
        artifact_path="artifacts/dataset_v4.parquet",
    )
    append_run_vector(breach_log, vec_breach)

    # Budget is 10.0 * 1.02 = 10.2s; wall is 50.0s -> must fail with EXIT_WALL_FAIL (14)
    proc_breach = subprocess.run(
        [
            sys.executable,
            "scripts/check_gates.py",
            "--runs-log",
            str(breach_log),
            "--export-budget",
            "10.0",
            "--budget-factor",
            "1.02",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc_breach.returncode == check_gates.EXIT_WALL_FAIL
    assert "GATE FAILURE" in proc_breach.stderr

    # Negative Control 3: Non-existent runs log
    proc_missing = subprocess.run(
        [
            sys.executable,
            "scripts/check_gates.py",
            "--runs-log",
            str(tmp_path / "non_existent.jsonl"),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc_missing.returncode == check_gates.EXIT_ERROR

    # Negative Control 4: Empty runs log
    empty_log = tmp_path / "empty.jsonl"
    empty_log.write_text("", encoding="utf-8")
    proc_empty = subprocess.run(
        [sys.executable, "scripts/check_gates.py", "--runs-log", str(empty_log)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc_empty.returncode == check_gates.EXIT_ERROR


def test_error_vector_emitted_on_failure(tmp_path: pathlib.Path) -> None:
    """When a job encounters a fatal error, an error vector is emitted to runs.jsonl before raising."""
    runs_log = tmp_path / "fail_runs.jsonl"

    # Trigger ValueError with banned full graph request
    with pytest.raises(ValueError, match="banned"):
        evidence.export_evidence(
            out_dir=tmp_path / "ev_banned",
            full_graph=True,
            runs_log=runs_log,
        )

    assert runs_log.exists()
    lines = runs_log.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    data = json.loads(lines[0])
    assert data["job_name"] == "evidence"
    assert data["status"] == "error"
    assert data["wall_seconds"] > 0
    assert data["peak_rss_kb"] > 0


def test_no_timing_assertions_in_this_file() -> None:
    """ABSOLUTE RULE: verify this test file does not assert timing threshold bounds."""
    import ast

    this_file = pathlib.Path(__file__)
    tree = ast.parse(this_file.read_text(encoding="utf-8"))

    # Traverse all Assert nodes and verify none test upper timing bounds on wall seconds
    for node in ast.walk(tree):
        if isinstance(node, ast.Assert) and isinstance(node.test, ast.Compare):
            left_str = ast.unparse(node.test.left)
            for op in node.test.ops:
                if isinstance(op, (ast.Lt, ast.LtE)):
                    assert "wall" not in left_str.lower(), (
                        f"Precedent violation: upper timing threshold bound assert '{ast.unparse(node)}' "
                        f"found in {this_file.name}. See test_twin_w6_determinism_wall.py:7-9 precedent."
                    )
