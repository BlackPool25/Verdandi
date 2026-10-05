"""Causal evidence window extraction and floor verification module (Todo 5 / P0-2).

Normative specifications & constraints:
1. Exactly 4 causal evidence windows: ("line-A", "line-B", "line-C", "cell").
   Citing SIM_SPEC §10 vs twin.py:119: twin router returns "rework" for RWK*
   machines, but causal discovery (§10) treats rework as part of the "cell"
   partition.
2. Explicit partition remapping: the evidence layer MUST explicitly remap
   "rework" -> "cell", leaving the frozen twin router and _PARTITIONS untouched.
   A dedicated test asserts RWK0 rows are placed inside the "cell" window.
3. Causal evidence floor: every partition window has n >= 800 clean steps (N_FLOOR=800).
   Attempts to generate or export evidence with n < 800 must raise ValueError loudly.
4. Full-graph request rejection: requesting full-graph causal evidence is BANNED
   (O(P^2 * tau) complexity explosion) and MUST raise ValueError loudly.
5. Node count cap: each partition window has node count <= 10 (NODE_CAP=10).
6. Unknown partition rejection: invalid or unknown partition names raise ValueError loudly.
7. Manifest metadata: per-window manifest containing partition, n_steps >= 800,
   seeds hash, schema, pyarrow version.
8. Parquet writer hardening: version="2.6", coerce_timestamps="us", use_dictionary=False.
9. Guardrails: raw channels only (obs, state, buffer, tput, currents - NO aggregates like
   mean/RMS/envelope), zero external causal library dependency, and frozen twin physics preserved.
10. CLI execution contract: python -m src.evidence --out <dir> supports argparse and exits 0 on --help.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys
import time
import uuid
from collections.abc import Sequence
from typing import Any

import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.parquet as pq  # type: ignore[import-untyped]

from src import config, twin
from src.calibrate import append_run_vector, get_peak_rss_kb, make_run_vector

# Normative causal partitions (SIM_SPEC §10, 4 windows)
CAUSAL_PARTITIONS: tuple[str, ...] = ("line-A", "line-B", "line-C", "cell")

# Causal evidence floor per window (SIM_SPEC §7.4, KQ1: 400 unstable, 800 stable)
N_FLOOR: int = 800

# Per-partition node count ceiling (SIM_SPEC §10)
NODE_CAP: int = 10

# Banned full-graph request strings (O(P^2 * tau) complexity explosion)
BANNED_FULL_GRAPH_REQUESTS: frozenset[str] = frozenset(
    {"full", "full-graph", "all", "plant", "full_graph"}
)


# =============================================================================
# PARTITION REMAPPING: "rework" -> "cell"
#
# Citing SIM_SPEC §10 vs twin.py:119:
# The frozen twin simulation router (_partition_of_machine at twin.py:2406-2425)
# returns "rework" for RWK* machines (such as RWK0), and twin._PARTITIONS has
# 5 entries ("line-A", "line-B", "line-C", "cell", "rework").
# However, causal discovery (SIM_SPEC §10) strictly defines 4 causal evidence
# partitions: ("line-A", "line-B", "line-C", "cell"). SIM_SPEC §10 treats rework
# as part of the "cell" partition (along with ASM0, ASM1, INSP0, ASM2).
#
# To preserve the frozen twin physics, router, and _PARTITIONS without mutation,
# the causal evidence layer explicitly remaps "rework" -> "cell".
# Consequently, RWK0 channels and rows are placed inside the "cell" partition window.
# =============================================================================


def remap_partition(name: str) -> str:
    """Remap simulation partition names to causal evidence partition windows.

    Citing SIM_SPEC §10 vs twin.py:119:
    Twin router returns 'rework' for RWK* machines, but causal discovery (§10)
    treats rework as part of the 'cell' partition window.
    """
    if name == "rework":
        return "cell"
    if name in CAUSAL_PARTITIONS:
        return name
    raise ValueError(
        f"Unknown or invalid partition: {name!r}. "
        f"Expected 'rework' or one of {CAUSAL_PARTITIONS}."
    )


def partition_of_machine(name: str) -> str:
    """Return the causal evidence partition for a given machine name.

    Explicitly remaps 'rework' -> 'cell' (SIM_SPEC §10 vs twin.py:119).
    """
    twin_part = twin._partition_of_machine(name)
    return remap_partition(twin_part)


def get_partition_machines(partition: str) -> list[str]:
    """Return the list of machine names assigned to a causal evidence partition window.

    Raises ValueError if partition is unknown or not in CAUSAL_PARTITIONS.
    Note: 'rework' is not an allowed causal partition window; RWK* machines are in 'cell'.
    """
    if partition not in CAUSAL_PARTITIONS:
        raise ValueError(
            f"Unknown or invalid partition: {partition!r}. "
            f"Must be one of {CAUSAL_PARTITIONS}."
        )
    return [m for m in config.MACHINE_INDEX if partition_of_machine(m) == partition]


def validate_evidence_floor(n_steps: int) -> int:
    """Validate that causal evidence step count satisfies N_FLOOR."""
    if n_steps < N_FLOOR:
        raise ValueError(
            f"Causal evidence floor violated: n_steps={n_steps} < N_FLOOR={N_FLOOR}. "
            f"Each causal evidence partition window must have at least {N_FLOOR} clean steps."
        )
    return n_steps


def validate_node_cap(nodes: Sequence[Any]) -> list[Any]:
    """Validate that partition node count does not exceed NODE_CAP."""
    node_list = list(nodes)
    if len(node_list) > NODE_CAP:
        raise ValueError(
            f"Partition node count cap exceeded: {len(node_list)} nodes > NODE_CAP={NODE_CAP}."
        )
    return node_list


def export_evidence(
    out_dir: str | pathlib.Path = "artifacts/evidence_v4/",
    seeds: Sequence[int] | None = None,
    partition: str | None = None,
    full_graph: bool = False,
    exclude_warmup: bool = True,
    compression: str = "snappy",
    row_group_size: int = 5000,
    runs_log: str | pathlib.Path | None = None,
) -> dict[str, Any]:
    """Export raw causal evidence windows and manifest metadata.

    Parameters:
        out_dir: Destination directory for parquet files and manifest.
        seeds: Optional sequence of episode seeds (defaults to config.SEEDS_20).
        partition: Optional single causal partition to export.
        full_graph: Banned flag; raises ValueError if True.
        exclude_warmup: Whether to exclude transient warm-up steps.
        compression: Parquet compression codec (defaults to 'snappy').
        row_group_size: Parquet row group size.
        runs_log: Optional path to runs.jsonl log for wall/RSS vectors.

    Returns:
        Dictionary containing manifest documentation, windows, and output paths.
    """
    run_id = f"run-{int(time.time())}-{uuid.uuid4().hex[:8]}"
    start_time = time.perf_counter()
    out_path = pathlib.Path(out_dir)

    try:
        # 1. Banned full-graph request check
        if full_graph or (
            partition is not None
            and str(partition).lower() in BANNED_FULL_GRAPH_REQUESTS
        ):
            raise ValueError(
                "Full-graph causal discovery request is banned due to O(P^2 * tau) complexity explosion. "
                "Causal evidence discovery must run per partition."
            )

        # 2. Partition validation
        target_partitions: list[str]
        if partition is not None:
            if partition not in CAUSAL_PARTITIONS:
                raise ValueError(
                    f"Unknown or invalid partition: {partition!r}. "
                    f"Must be one of {CAUSAL_PARTITIONS}."
                )
            target_partitions = [partition]
        else:
            target_partitions = list(CAUSAL_PARTITIONS)

        # 3. Seed validation & step configuration
        target_seeds: list[int]
        if seeds is None:
            target_seeds = list(config.SEEDS_20)
        else:
            target_seeds = list(seeds)

        seeds_str = ",".join(str(s) for s in target_seeds)
        seeds_hash = hashlib.sha256(seeds_str.encode("utf-8")).hexdigest()

        step_range = (
            range(config.WARMUP_STEPS, config.T) if exclude_warmup else range(config.T)
        )

        total_steps = len(target_seeds) * len(step_range)
        validate_evidence_floor(total_steps)

        out_path.mkdir(parents=True, exist_ok=True)

        # 4. Generate clean episode records
        episode_records: list[dict[str, Any]] = []
        for s in target_seeds:
            rec = twin.run_episode(s, None, enable_natural_breakdown=False)
            episode_records.append(rec)

        manifest_windows: list[dict[str, Any]] = []
        manifest_by_part: dict[str, Any] = {}

        # 5. Extract and export each partition window
        for part in target_partitions:
            part_machines = get_partition_machines(part)
            validate_node_cap(part_machines)

            # Raw channels only: obs, state, buffer, tput, currents
            columns_data: dict[str, list[Any]] = {
                "seed": [],
                "step": [],
            }
            for m in part_machines:
                columns_data[f"obs_{m}"] = []
                columns_data[f"state_{m}"] = []
                columns_data[f"buffer_{m}"] = []
                columns_data[f"tput_{m}"] = []
                columns_data[f"current_{m}"] = []

            for rec in episode_records:
                seed_val = int(rec["seed"])
                for t_step in step_range:
                    columns_data["seed"].append(seed_val)
                    columns_data["step"].append(int(t_step))
                    for m in part_machines:
                        m_idx = config.MACHINE_INDEX[m]
                        columns_data[f"obs_{m}"].append(
                            float(rec["obs"][m_idx][t_step])
                        )
                        columns_data[f"state_{m}"].append(
                            str(rec["states"][m_idx][t_step])
                        )
                        columns_data[f"buffer_{m}"].append(
                            int(rec["buffers"][m_idx][t_step])
                        )
                        columns_data[f"tput_{m}"].append(
                            int(rec["throughput"][m_idx][t_step])
                        )
                        columns_data[f"current_{m}"].append(
                            float(rec["currents"][m_idx][t_step])
                        )

            n_rows = len(columns_data["seed"])
            validate_evidence_floor(n_rows)

            # Deterministic sorted column order
            sorted_cols = sorted(columns_data.keys())
            table = pa.Table.from_pydict({c: columns_data[c] for c in sorted_cols})

            # Harden Parquet writer: version="2.6", coerce_timestamps="us", use_dictionary=False
            part_file = out_path / f"{part}.parquet"
            pq.write_table(
                table,
                str(part_file),
                version="2.6",
                coerce_timestamps="us",
                use_dictionary=False,
                compression=compression,
                row_group_size=row_group_size,
            )

            with open(part_file, "rb") as f:
                file_sha256 = hashlib.sha256(f.read()).hexdigest()

            entry = {
                "partition": part,
                "n_steps": n_rows,
                "seeds_hash": seeds_hash,
                "schema": config.TWIN_SCHEMA,
                "schema_version": config.TWIN_SCHEMA,
                "pyarrow_version": pa.__version__,
                "file": f"{part}.parquet",
                "sha256": file_sha256,
                "nodes": part_machines,
                "channels": ["obs", "state", "buffer", "tput", "current"],
            }
            manifest_windows.append(entry)
            manifest_by_part[part] = entry

            # Per-window manifest sidecar
            part_meta_path = out_path / f"{part}_manifest.json"
            with open(part_meta_path, "w", encoding="utf-8") as f:
                json.dump(entry, f, indent=2, sort_keys=True)

        # 6. Master manifest
        manifest_doc = {
            "schema": config.TWIN_SCHEMA,
            "schema_version": config.TWIN_SCHEMA,
            "pyarrow_version": pa.__version__,
            "seeds_hash": seeds_hash,
            "windows": manifest_windows,
        }
        master_manifest_path = out_path / "manifest.json"
        with open(master_manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest_doc, f, indent=2, sort_keys=True)

        wall_sec = time.perf_counter() - start_time
        rss_kb = get_peak_rss_kb()
        vector = make_run_vector(
            run_id=run_id,
            job_name="evidence",
            wall_seconds=wall_sec,
            peak_rss_kb=rss_kb,
            status="success",
            artifact_path=str(out_path),
            schema_version=config.TWIN_SCHEMA,
        )
        if runs_log is not None:
            append_run_vector(runs_log, vector)

        return {
            "by_partition": manifest_by_part,
            "manifest": manifest_doc,
            "out_dir": str(out_path),
            "peak_rss_kb": rss_kb,
            "peak_rss_mb": vector["peak_rss_mb"],
            "run_id": run_id,
            "run_vector": vector,
            "wall_seconds": vector["wall_seconds"],
            "windows": manifest_windows,
        }
    except Exception:
        wall_sec = time.perf_counter() - start_time
        rss_kb = get_peak_rss_kb()
        err_vector = make_run_vector(
            run_id=run_id,
            job_name="evidence",
            wall_seconds=wall_sec,
            peak_rss_kb=rss_kb,
            status="error",
            artifact_path=str(out_path),
            schema_version=config.TWIN_SCHEMA,
        )
        if runs_log is not None:
            append_run_vector(runs_log, err_vector)
        raise


def build_parser() -> argparse.ArgumentParser:
    """Build command line argument parser for evidence export CLI."""
    parser = argparse.ArgumentParser(
        description="Export per-partition causal evidence windows (SIM_SPEC §10)."
    )
    parser.add_argument(
        "--out",
        type=str,
        default="artifacts/evidence_v4/",
        help="Output directory for causal evidence Parquet files and manifest.",
    )
    parser.add_argument(
        "--partition",
        type=str,
        default=None,
        help="Optional single partition to export (line-A, line-B, line-C, cell).",
    )
    parser.add_argument(
        "--runs-log",
        type=str,
        default="artifacts/runs.jsonl",
        help="Path to runs JSONL log file (default: artifacts/runs.jsonl)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Main CLI entrypoint for causal evidence extraction."""
    parser = build_parser()
    args = parser.parse_args(argv)
    export_evidence(
        out_dir=args.out,
        partition=args.partition,
        runs_log=args.runs_log,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
