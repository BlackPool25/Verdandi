"""Calibration module for twin simulation with deterministic Parquet export and schema-v4 binding.

Normative requirements:
1. Deterministic Re-capture:
   - Same-seed re-capture produces byte-identical Parquet artifact and sidecar metadata (sha256 matching).
2. Artifact & Metadata Binding:
   - Artifact sidecar carries schema_version (4), code_version (config.CODE_VERSION),
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
   - Writer uses version='2.6', coerce_timestamps='us', fixed use_dictionary=False, and compression='snappy'.
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

import argparse
import datetime
import fcntl
import hashlib
import json
import os
import pathlib
import resource
import time
import uuid
from collections.abc import Sequence
from typing import Any

import numpy as np
import pandas as pd  # type: ignore[import-untyped]
import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.parquet as pq  # type: ignore[import-untyped]

from src import config
from src.twin import run_episode

PERCENTILE_GRID: tuple[float, ...] = (0.5, 0.9, 0.95, 0.98, 0.99, 0.995)


def get_peak_rss_kb() -> float:
    """Return peak process RSS in kilobytes using stdlib resource."""
    return float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)


def append_run_vector(runs_log: str | pathlib.Path, vector: dict[str, Any]) -> None:
    """Atomically append a run vector line to runs.jsonl using POSIX file locking (xdist-safe)."""
    path = pathlib.Path(runs_log)
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(vector, sort_keys=True) + "\n"
    with open(path, "a", encoding="utf-8") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            f.write(line)
            f.flush()
            os.fsync(f.fileno())
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def make_run_vector(
    run_id: str,
    job_name: str,
    wall_seconds: float,
    peak_rss_kb: float,
    status: str,
    artifact_path: str,
    schema_version: int = config.TWIN_SCHEMA,
    code_version: str = config.CODE_VERSION,
) -> dict[str, Any]:
    """Construct a standardized run vector dictionary."""
    peak_rss_mb = round(peak_rss_kb / 1024.0, 2)
    return {
        "artifact_path": str(artifact_path),
        "code_version": str(code_version),
        "job_name": str(job_name),
        "peak_rss_kb": float(peak_rss_kb),
        "peak_rss_mb": float(peak_rss_mb),
        "run_id": str(run_id),
        "schema_version": int(schema_version),
        "status": str(status),
        "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
        "wall_seconds": round(max(float(wall_seconds), 1e-5), 6),
    }


def calibrate(
    seeds: Sequence[int] | None = None,
    out: str | pathlib.Path = "artifacts/cal_v4.parquet",
    schema_version: int = config.TWIN_SCHEMA,
    runs_log: str | pathlib.Path | None = None,
) -> dict[str, Any]:
    """Capture calibration windows over seeds on fault-free twin runs and export Parquet + JSON sidecar.

    Args:
        seeds: Optional sequence of integer RNG seeds (default: config.SEEDS_20).
        out: Path to the target Parquet artifact.
        schema_version: Twin schema version to bind (must be >= 4).
        runs_log: Optional path to runs.jsonl log for wall/RSS vectors.

    Returns:
        Dictionary containing dataset_hash (sha256 of the parquet file), file path,
        summary stats, and run vector details.
    """
    run_id = f"run-{int(time.time())}-{uuid.uuid4().hex[:8]}"
    start_time = time.perf_counter()
    out_path = pathlib.Path(out)

    try:
        if schema_version < 4:
            raise ValueError(
                f"Unsupported schema_version {schema_version}: must be >= 4 (current {config.TWIN_SCHEMA})"
            )

        if seeds is None:
            target_seeds = list(config.SEEDS_20)
        else:
            target_seeds = [int(s) for s in seeds]

        out_path.parent.mkdir(parents=True, exist_ok=True)

        rows: list[dict[str, Any]] = []

        for seed in target_seeds:
            rec = run_episode(seed, None, enable_natural_breakdown=False)
            raw_obs = np.asarray(rec["obs"], dtype=float)  # shape (26, 300)

            # Exclude warm-up steps: clean calibration window is WARMUP_STEPS to CAL_WIN
            for t in range(config.WARMUP_STEPS, config.CAL_WIN):
                row: dict[str, Any] = {
                    "seed": seed,
                    "step": t,
                }
                for m_name, m_idx in config.MACHINE_INDEX.items():
                    row[f"obs_{m_name}"] = float(raw_obs[m_idx, t])
                rows.append(row)

        df = pd.DataFrame(rows)
        # Normative requirement: sorted column keys for determinism
        sorted_cols = sorted(df.columns)
        df = df[sorted_cols]

        # Convert to PyArrow table and write with hardened options
        table = pa.Table.from_pandas(df, preserve_index=False)
        pq.write_table(
            table,
            str(out_path),
            version="2.6",
            coerce_timestamps="us",
            use_dictionary=False,
            compression="snappy",
            row_group_size=65536,
        )

        # Compute deterministic SHA256 digest of the Parquet artifact
        with open(out_path, "rb") as f:
            dataset_hash = hashlib.sha256(f.read()).hexdigest()

        # Calculate percentile grid and min/max per machine across calibration piles
        machines_summary: dict[str, dict[str, Any]] = {}
        for m_name in config.MACHINE_INDEX:
            col = f"obs_{m_name}"
            raw_vals = df[col].to_numpy()
            pcts: dict[str, float] = {
                str(p): float(np.percentile(raw_vals, p * 100.0))
                for p in PERCENTILE_GRID
            }
            machines_summary[m_name] = {
                "min": float(np.min(raw_vals)),
                "max": float(np.max(raw_vals)),
                "percentiles": pcts,
            }

        seed_list_hash = hashlib.sha256(
            json.dumps(target_seeds).encode("utf-8")
        ).hexdigest()

        # Sidecar metadata dictionary
        meta: dict[str, Any] = {
            "code_version": config.CODE_VERSION,
            "machines": machines_summary,
            "pyarrow_version": pa.__version__,
            "row_count": len(df),
            "schema_version": int(schema_version),
            "seed_list_hash": seed_list_hash,
            "seeds": target_seeds,
            "seeds_hash": seed_list_hash,
            "sha256": dataset_hash,
            "summary": machines_summary,
        }

        sidecar_path = out_path.with_suffix(".json")
        with open(sidecar_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2, sort_keys=True)

        # Leakage law assert: absolute rule that NO scaler.pkl exists anywhere
        scaler_artifact = pathlib.Path("artifacts/scaler.pkl")
        if scaler_artifact.exists():
            raise RuntimeError("LEAKAGE VIOLATION: scaler.pkl exists in artifacts/")

        wall_sec = time.perf_counter() - start_time
        rss_kb = get_peak_rss_kb()
        vector = make_run_vector(
            run_id=run_id,
            job_name="calibrate",
            wall_seconds=wall_sec,
            peak_rss_kb=rss_kb,
            status="success",
            artifact_path=str(out_path),
            schema_version=int(schema_version),
        )

        if runs_log is not None:
            append_run_vector(runs_log, vector)

        return {
            "dataset_hash": dataset_hash,
            "out": str(out_path),
            "peak_rss_kb": rss_kb,
            "peak_rss_mb": vector["peak_rss_mb"],
            "row_count": len(df),
            "run_id": run_id,
            "run_vector": vector,
            "sha256": dataset_hash,
            "sidecar_path": str(sidecar_path),
            "wall_seconds": vector["wall_seconds"],
        }
    except Exception:
        wall_sec = time.perf_counter() - start_time
        rss_kb = get_peak_rss_kb()
        err_vector = make_run_vector(
            run_id=run_id,
            job_name="calibrate",
            wall_seconds=wall_sec,
            peak_rss_kb=rss_kb,
            status="error",
            artifact_path=str(out_path),
            schema_version=int(schema_version)
            if isinstance(schema_version, int)
            else 4,
        )
        if runs_log is not None:
            append_run_vector(runs_log, err_vector)
        raise


def load_calibration(
    parquet_path: str | pathlib.Path,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Load calibration Parquet artifact and sidecar metadata with strict integrity checks.

    Args:
        parquet_path: Path to the Parquet artifact.

    Returns:
        Tuple of (DataFrame, metadata_dict).

    Raises:
        ValueError: If sidecar JSON is missing, corrupted, checksum mismatches,
            or schema_version < 4.
    """
    path = pathlib.Path(parquet_path)
    if not path.exists():
        raise ValueError(f"Parquet file missing at {path}")

    sidecar_path = path.with_suffix(".json")
    if not sidecar_path.exists():
        raise ValueError(f"Sidecar metadata missing at {sidecar_path}")

    try:
        meta = json.loads(sidecar_path.read_text(encoding="utf-8"))
    except Exception as err:
        raise ValueError(f"Corrupt metadata JSON at {sidecar_path}: {err}") from err

    schema_version = meta.get("schema_version")
    if schema_version is None or int(schema_version) < 4:
        raise ValueError(
            f"Unsupported schema_version {schema_version} in metadata (expected >= 4)"
        )

    with open(path, "rb") as f:
        actual_sha = hashlib.sha256(f.read()).hexdigest()

    expected_sha = meta.get("sha256")
    if expected_sha != actual_sha:
        raise ValueError(
            f"Parquet sha256 checksum mismatch: metadata {expected_sha} != actual {actual_sha}"
        )

    table = pq.read_table(str(path))
    df = table.to_pandas()
    return df, meta


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entrypoint for calibration module."""
    parser = argparse.ArgumentParser(
        description="Run twin calibration on clean windows and export Parquet artifact + sidecar JSON."
    )
    parser.add_argument(
        "--out",
        type=str,
        default="artifacts/cal_v4.parquet",
        help="Path to output Parquet calibration artifact (e.g. artifacts/cal_v4.parquet)",
    )
    parser.add_argument(
        "--seeds",
        type=int,
        nargs="+",
        default=None,
        help="List of RNG seeds for calibration episodes (default: config.SEEDS_20)",
    )
    parser.add_argument(
        "--schema-version",
        type=int,
        default=config.TWIN_SCHEMA,
        help="Twin schema version (must be >= 4, default: config.TWIN_SCHEMA)",
    )
    parser.add_argument(
        "--runs-log",
        type=str,
        default="artifacts/runs.jsonl",
        help="Path to runs JSONL log file (default: artifacts/runs.jsonl)",
    )
    args = parser.parse_args(argv)
    seeds = args.seeds if args.seeds is not None else list(config.SEEDS_20)
    calibrate(
        seeds=seeds,
        out=args.out,
        schema_version=args.schema_version,
        runs_log=args.runs_log,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
