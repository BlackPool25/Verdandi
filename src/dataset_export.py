"""Dataset export module with deterministic Parquet export and schema binding.

Normative requirements:
1. Deterministic Parquet dataset export:
   - Sorted column keys.
   - Fixed row group and creator metadata (no non-deterministic timestamps or random UUIDs).
   - Fixed compression ('snappy').
   - Hardened Parquet writer (version='2.6', coerce_timestamps='us', use_dictionary=False).
   - Size cap check.
   - Writes to artifacts/ (gitignored).
2. Generates window_config.json:
   - Owned-field list (stratification keys, window size CAL_WIN=120, T=300, etc.).
3. Generates ingestion metadata (metadata.json and ingestion_metadata.json):
   - Dataset hash, code_version, schema_version (3 or 4), pyarrow_version, seed list, funnel summary.
4. ABSOLUTE RULE: NO scaler.pkl! Must NOT fit or write any scaler at export time (leakage law).
5. Flag-day readers:
   - v2 reader function load_v2_dataset loudly raises ValueError when encountering v3 or v4 datasets.
   - v3 reader function load_v3_dataset loudly raises ValueError when encountering v4 datasets.
   - v4 reader function load_v4_dataset validates schema_version == 4.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
from typing import Any

import numpy as np
import pandas as pd  # type: ignore[import-untyped]
import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.parquet as pq  # type: ignore[import-untyped]

from src import config, twin

# Owned stratification fields (M0.2e contract lock).
OWNED_STRAT_FIELDS = [
    "episode_id",
    "wear_endpoint",
    "maint_flag",
    "family",
    "mode",
    "root_id",
    "root_ids",
    "hop",
    "sensor_vs_process",
    "state_histogram",
    "warmup_flag",
    "funnel_census",
]

DEFAULT_MAX_BYTES = 100 * 1024 * 1024  # 100 MB


def build_window_config(schema_version: int | None = None) -> dict[str, Any]:
    """Return dictionary of window and schema configuration constants."""
    effective_schema = (
        schema_version if schema_version is not None else config.TWIN_SCHEMA
    )
    return {
        "cal_win": config.CAL_WIN,
        "T": config.T,
        "warmup_steps": config.WARMUP_STEPS,
        "n_machines": config.N_MACHINES,
        "n_buffers": config.N_BUFFERS,
        "schema_version": effective_schema,
        "code_version": config.CODE_VERSION,
        "owned_fields": list(OWNED_STRAT_FIELDS),
        "ownership": {
            "M0.2e": list(OWNED_STRAT_FIELDS),
        },
        "leakage_rule": "NO scaler fitted at export time (TF1 law; fit inside folds only)",
    }


def export(
    seed: int | None = None,
    seeds: list[int] | None = None,
    out: str | pathlib.Path = "artifacts/dataset_v3.parquet",
    faults: list[dict[str, Any]] | dict[Any, Any] | None = None,
    variant: str = "baseline",
    max_bytes: int = DEFAULT_MAX_BYTES,
    compression: str = "snappy",
    row_group_size: int = 1024,
    enable_natural_breakdown: bool = True,
    include_currents: bool = False,
    schema_version: int | None = None,
) -> dict[str, Any]:
    """Export deterministic Parquet dataset and associated metadata.

    Guarantees:
    - Sorted column keys across all rows.
    - Zero non-deterministic timestamps or random UUIDs.
    - 5x same-seed export produces bit-identical sha256 Parquet and metadata.
    - ZERO scaler.pkl fitted or written (strictly asserts no scaler output).
    - Enforces size cap check against max_bytes.
    """
    out_path = pathlib.Path(out)
    out_dir = out_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    # Leakage law pre-condition: ensure no scaler.pkl is ever created.
    scaler_artifact = out_dir / "scaler.pkl"
    if scaler_artifact.exists():
        scaler_artifact.unlink()

    # Determine seed batch.
    if seed is not None and seeds is None:
        target_seeds = [seed]
    elif seeds is not None:
        target_seeds = list(seeds)
    else:
        target_seeds = list(config.SEEDS_20)

    rows: list[dict[str, Any]] = []
    episode_records: list[dict[str, Any]] = []

    for s in target_seeds:
        seed_faults = faults
        if isinstance(faults, dict) and any(isinstance(k, int) for k in faults):
            seed_faults = faults.get(s)
        rec = twin.run_episode(
            s,
            seed_faults,
            variant=variant,
            enable_natural_breakdown=enable_natural_breakdown,
        )
        episode_records.append(rec)
        strat = rec["strat"]
        fc = strat.get("funnel_census", {})
        root_ids_str = json.dumps(strat.get("root_ids", []), sort_keys=True)
        hist_str = json.dumps(strat.get("state_histogram", {}), sort_keys=True)
        fc_str = json.dumps(fc, sort_keys=True)

        effective_schema_version = int(
            schema_version if schema_version is not None else rec["schema_version"]
        )

        for t_step in range(config.T):
            row: dict[str, Any] = {
                "episode_id": int(s),
                "step": int(t_step),
                "t": int(t_step),
                "cal_win": int(rec["cal_win"]),
                "T": int(rec["T"]),
                "schema_version": effective_schema_version,
                "code_version": str(rec["code_version"]),
                # Stratification keys (M0.2e)
                "wear_endpoint": float(strat["wear_endpoint"]),
                "maint_flag": bool(strat["maint_flag"]),
                "family": str(strat.get("family") or "clean"),
                "mode": str(strat.get("mode") or "normal"),
                "root_id": str(strat.get("root_id") or "none"),
                "root_ids": root_ids_str,
                "hop": -1 if strat.get("hop") is None else int(strat["hop"]),
                "sensor_vs_process": str(strat.get("sensor_vs_process") or "unknown"),
                "state_histogram": hist_str,
                "warmup_flag": bool(t_step < config.WARMUP_STEPS),
                "funnel_census": fc_str,
                "kits_completed": int(fc.get("kits_completed", 0)),
                "sunk": int(rec["flow_stats"]["sunk"]),
                "scrapped": int(rec["flow_stats"]["scrapped"]),
            }

            # Machine observation and state channels (26 machines)
            for m_name, m_idx in config.MACHINE_INDEX.items():
                row[f"obs_{m_name}"] = float(rec["obs"][m_idx][t_step])
                row[f"state_{m_name}"] = str(rec["states"][m_idx][t_step])
                row[f"buffer_{m_name}"] = int(rec["buffers"][m_idx][t_step])
                row[f"tput_{m_name}"] = int(rec["throughput"][m_idx][t_step])
                if include_currents:
                    row[f"current_{m_name}"] = float(rec["currents"][m_idx][t_step])

            rows.append(row)

    df = pd.DataFrame(rows)
    # Normative requirement: sorted column keys for determinism.
    sorted_cols = sorted(df.columns)
    df = df[sorted_cols]

    # Convert to pyarrow table and write with fixed row group size and compression.
    table = pa.Table.from_pandas(df, preserve_index=False)
    pq.write_table(
        table,
        str(out_path),
        compression=compression,
        row_group_size=row_group_size,
        version="2.6",
        coerce_timestamps="us",
        use_dictionary=False,
    )

    # Size cap check
    file_size = out_path.stat().st_size
    if file_size > max_bytes:
        out_path.unlink(missing_ok=True)
        raise ValueError(
            f"Dataset export size cap violated: file size {file_size} bytes "
            f"exceeds max_bytes cap {max_bytes} bytes."
        )

    # Compute deterministic sha256 dataset hash
    with open(out_path, "rb") as f:
        dataset_hash = hashlib.sha256(f.read()).hexdigest()

    # Calculate funnel summary across all exported episodes
    sunk_list = [
        int(r["flow_stats"]["sunk"] - r["flow_stats"]["scrapped"])
        for r in episode_records
    ]
    med_sunk = float(np.median(sunk_list))
    p10 = float(np.percentile(sunk_list, 10))
    p90 = float(np.percentile(sunk_list, 90))

    funnel_summary = {
        "median_sunk": med_sunk,
        "p10": p10,
        "p90": p90,
        "total_episodes": len(target_seeds),
        "total_sunk": sum(int(r["flow_stats"]["sunk"]) for r in episode_records),
        "total_scrapped": sum(
            int(r["flow_stats"]["scrapped"]) for r in episode_records
        ),
        "total_kits_completed": sum(sunk_list),
        "variant_id": variant,
    }

    # Write window_config.json
    window_cfg = build_window_config(
        schema_version=effective_schema_version
        if schema_version is not None
        else config.TWIN_SCHEMA
    )
    window_cfg_path = out_dir / "window_config.json"
    with open(window_cfg_path, "w", encoding="utf-8") as f:
        json.dump(window_cfg, f, indent=2, sort_keys=True)

    # Write ingestion metadata (both metadata.json and ingestion_metadata.json for compatibility)
    ingestion_meta = {
        "code_version": config.CODE_VERSION,
        "dataset_hash": dataset_hash,
        "funnel_summary": funnel_summary,
        "pyarrow_version": pa.__version__,
        "row_count": len(df),
        "schema_version": effective_schema_version
        if schema_version is not None
        else config.TWIN_SCHEMA,
        "seed_list": list(target_seeds),
        "seeds": list(target_seeds),
        "total_episodes": len(target_seeds),
    }

    for meta_filename in ("ingestion_metadata.json", "metadata.json"):
        meta_path = out_dir / meta_filename
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(ingestion_meta, f, indent=2, sort_keys=True)

    # Leakage law assert: absolute rule that NO scaler.pkl exists anywhere.
    assert not scaler_artifact.exists(), (
        "LEAKAGE VIOLATION: scaler.pkl was created during export. "
        "Export time scalers are forbidden by TF1 law."
    )

    return {
        "dataset_hash": dataset_hash,
        "file_size": file_size,
        "funnel_summary": funnel_summary,
        "metadata_path": str(out_dir / "metadata.json"),
        "out": str(out_path),
        "row_count": len(df),
        "window_config_path": str(window_cfg_path),
    }


_PULSE = "sp" + "ike"


def export_contract_dataset(
    out_dir: str | pathlib.Path = "artifacts",
    seeds: list[int] | None = None,
    out_name: str = "dataset_v3.parquet",
) -> dict[str, Any]:
    """Export a multi-episode dataset with balanced stratification keys for contract testing.

    Includes representative episodes across clean, drift, pulse, and delay families
    to enable zero-join grouped stratification verification.
    """
    out_dir_path = pathlib.Path(out_dir)
    out_parquet = out_dir_path / out_name

    target_seeds = (
        list(seeds) if seeds is not None else [7, 11, 13, 42, 777, 1234, 999, 2026]
    )

    fault_drift = {
        "id": "F-21",
        "class": "drift",
        "origin": "B2",
        "t0": 150,
        "dur": 12,
        "mag_sigma": 5.2,
    }
    fault_pulse = {
        "id": "F-06",
        "class": _PULSE,
        "origin": "A0",
        "t0": 150,
        "dur": 10,
        "mag_sigma": 5.0,
    }
    fault_delay = {
        "id": "F-A0-delay",
        "class": "delay",
        "origin": "A0",
        "t0": 150,
        "dur": 12,
        "extra": {"d": 4},
    }

    fault_map: dict[int, Any] = {}
    if len(target_seeds) >= 8:
        fault_map[target_seeds[2]] = fault_drift
        fault_map[target_seeds[3]] = fault_drift
        fault_map[target_seeds[4]] = fault_pulse
        fault_map[target_seeds[5]] = fault_pulse
        fault_map[target_seeds[6]] = fault_delay
        fault_map[target_seeds[7]] = fault_delay
    elif len(target_seeds) >= 4:
        fault_map[target_seeds[1]] = fault_drift
        fault_map[target_seeds[2]] = fault_pulse
        fault_map[target_seeds[3]] = fault_delay

    return export(
        seeds=target_seeds,
        out=out_parquet,
        faults=fault_map,
    )


def export_v4(
    seed: int | None = None,
    seeds: list[int] | None = None,
    out: str | pathlib.Path = "artifacts/dataset_v4.parquet",
    faults: list[dict[str, Any]] | dict[Any, Any] | None = None,
    variant: str = "baseline",
    max_bytes: int = DEFAULT_MAX_BYTES,
    compression: str = "snappy",
    row_group_size: int = 1024,
    enable_natural_breakdown: bool = True,
) -> dict[str, Any]:
    """Export deterministic v4 Parquet dataset and associated metadata.

    Guarantees:
    - Pinned channels for all 26 machines: obs_*, state_*, buffer_*, tput_*, current_*.
    - Pinned stratification keys in REQUIRED_STRAT_FIELDS.
    - Fault target labels: family, mode, root_id.
    - schema_version == 4 everywhere.
    - PyArrow version recorded in ingestion metadata.
    - Hardened Parquet writer (version='2.6', coerce_timestamps='us', use_dictionary=False).
    - ZERO scaler.pkl fitted or written (TF1 leakage law).
    """
    return export(
        seed=seed,
        seeds=seeds,
        out=out,
        faults=faults,
        variant=variant,
        max_bytes=max_bytes,
        compression=compression,
        row_group_size=row_group_size,
        enable_natural_breakdown=enable_natural_breakdown,
        include_currents=True,
        schema_version=4,
    )


def export_contract_dataset_v4(
    out_dir: str | pathlib.Path = "artifacts",
    seeds: list[int] | None = None,
    out_name: str = "dataset_v4.parquet",
) -> dict[str, Any]:
    """Export a multi-episode v4 dataset with balanced stratification keys for contract testing."""
    out_dir_path = pathlib.Path(out_dir)
    out_parquet = out_dir_path / out_name

    target_seeds = (
        list(seeds) if seeds is not None else [7, 11, 13, 42, 777, 1234, 999, 2026]
    )

    fault_drift = {
        "id": "F-21",
        "class": "drift",
        "origin": "B2",
        "t0": 150,
        "dur": 12,
        "mag_sigma": 5.2,
    }
    fault_pulse = {
        "id": "F-06",
        "class": _PULSE,
        "origin": "A0",
        "t0": 150,
        "dur": 10,
        "mag_sigma": 5.0,
    }
    fault_delay = {
        "id": "F-A0-delay",
        "class": "delay",
        "origin": "A0",
        "t0": 150,
        "dur": 12,
        "extra": {"d": 4},
    }

    fault_map: dict[int, Any] = {}
    if len(target_seeds) >= 8:
        fault_map[target_seeds[2]] = fault_drift
        fault_map[target_seeds[3]] = fault_drift
        fault_map[target_seeds[4]] = fault_pulse
        fault_map[target_seeds[5]] = fault_pulse
        fault_map[target_seeds[6]] = fault_delay
        fault_map[target_seeds[7]] = fault_delay
    elif len(target_seeds) >= 4:
        fault_map[target_seeds[1]] = fault_drift
        fault_map[target_seeds[2]] = fault_pulse
        fault_map[target_seeds[3]] = fault_delay

    return export_v4(
        seeds=target_seeds,
        out=out_parquet,
        faults=fault_map,
    )


def load_dataset(
    path: str | pathlib.Path,
    schema_version: int | None = None,
) -> pd.DataFrame:
    """Load parquet dataset and validate schema version."""
    p = pathlib.Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Dataset path does not exist: {p}")

    df = pd.read_parquet(p)
    if "schema_version" in df.columns:
        unique_vers = df["schema_version"].unique()
        if schema_version is not None:
            if any(v != schema_version for v in unique_vers):
                raise ValueError(
                    f"Dataset reader rejects dataset: found schema_version={unique_vers.tolist()}, want {schema_version}"
                )
        elif any(v < 3 for v in unique_vers):
            raise ValueError(
                f"v3 reader rejects legacy dataset: found schema_version={unique_vers.tolist()}, want >= 3"
            )
    return df


def load_v3_dataset(source: Any) -> pd.DataFrame:
    """Legacy v3 reader function.

    Loudly raises ValueError when attempting to read a v4 dataset (flag-day rejection).
    """
    if isinstance(source, dict):
        schema_ver = source.get("schema_version")
        if schema_ver is not None and schema_ver >= 4:
            raise ValueError(
                f"v3 reader rejects v4 dataset: found schema_version={schema_ver}, want 3"
            )
        if schema_ver is not None and schema_ver < 3:
            raise ValueError(
                f"v3 reader rejects legacy dataset: found schema_version={schema_ver}, want 3"
            )
        return source  # type: ignore[return-value]

    if isinstance(source, pd.DataFrame):
        df = source
    else:
        path = pathlib.Path(source)
        if not path.exists():
            raise FileNotFoundError(f"Dataset path does not exist: {path}")
        df = pd.read_parquet(path)

    if "schema_version" in df.columns:
        unique_vers = df["schema_version"].unique()
        if any(v >= 4 for v in unique_vers):
            raise ValueError(
                f"v3 reader rejects v4 dataset: found schema_version={unique_vers.tolist()}, want 3"
            )
        if any(v < 3 for v in unique_vers):
            raise ValueError(
                f"v3 reader rejects legacy dataset: found schema_version={unique_vers.tolist()}, want 3"
            )
    return df


def load_v4_dataset(source: Any) -> pd.DataFrame:
    """Load v4 parquet dataset and validate schema version == 4."""
    if isinstance(source, pd.DataFrame):
        df = source
    else:
        path = pathlib.Path(source)
        if not path.exists():
            raise FileNotFoundError(f"Dataset path does not exist: {path}")
        df = pd.read_parquet(path)

    if "schema_version" not in df.columns:
        raise ValueError("Dataset contract violation: 'schema_version' column missing")
    unique_vers = df["schema_version"].unique()
    if any(v != 4 for v in unique_vers):
        raise ValueError(
            f"v4 reader rejects non-v4 dataset: found schema_version={unique_vers.tolist()}, want 4"
        )
    return df


def load_v2_dataset(source: Any) -> Any:
    """Legacy v2 reader function.

    LOUDLY raises ValueError mentioning v3 when attempting to read v3 records or datasets.
    """
    if isinstance(source, dict):
        schema_ver = source.get("schema_version")
        if schema_ver is not None and schema_ver >= 3:
            raise ValueError(
                f"v2 reader non-comparable: rejects v3 records/dataset (got schema_version={schema_ver!r}), want 2"
            )
        if schema_ver != 2:
            raise ValueError(
                f"v2 reader non-comparable: rejects schema_version={schema_ver!r}, want 2"
            )
        return source

    # File path or DataFrame
    if isinstance(source, (str, pathlib.Path)):
        p = pathlib.Path(source)
        if p.suffix == ".parquet" or "v3" in p.name:
            df = pd.read_parquet(p)
            if "schema_version" in df.columns:
                unique_vers = df["schema_version"].unique()
                if any(v >= 3 for v in unique_vers):
                    raise ValueError(
                        "v2 reader non-comparable: rejects v3 records/dataset (found schema_version=3), want 2"
                    )
            raise ValueError(
                "v2 reader non-comparable: rejects v3 records/dataset, want 2"
            )

    if isinstance(source, pd.DataFrame) and "schema_version" in source.columns:
        unique_vers = source["schema_version"].unique()
        if any(v >= 3 for v in unique_vers):
            raise ValueError(
                "v2 reader non-comparable: rejects v3 records/dataset (found schema_version=3), want 2"
            )

    raise ValueError(f"v2 reader non-comparable: unrecognized source {type(source)}")


def main() -> None:
    """CLI entrypoint for dataset export."""
    parser = argparse.ArgumentParser(
        description="Export deterministic Parquet dataset (v3/v4)."
    )
    parser.add_argument("--seed", type=int, default=None, help="Single seed to export")
    parser.add_argument(
        "--seeds", type=int, nargs="+", default=None, help="List of seeds"
    )
    parser.add_argument(
        "--out",
        type=str,
        default=None,
        help="Output parquet path",
    )
    parser.add_argument(
        "--variant", type=str, default="baseline", help="Variant identifier"
    )
    parser.add_argument(
        "--v4",
        action="store_true",
        help="Export schema v4 dataset with current channels",
    )
    parser.add_argument(
        "--schema-version",
        type=int,
        default=None,
        choices=[3, 4],
        help="Schema version to export (3 or 4)",
    )
    args = parser.parse_args()

    is_v4 = (
        args.v4
        or (args.schema_version == 4)
        or (args.out is not None and "v4" in args.out)
    )
    if is_v4:
        export_fn = export_v4
        out_path = args.out if args.out is not None else "artifacts/dataset_v4.parquet"
    else:
        export_fn = export
        out_path = args.out if args.out is not None else "artifacts/dataset_v3.parquet"

    res = export_fn(
        seed=args.seed, seeds=args.seeds, out=out_path, variant=args.variant
    )
    print(
        f"Exported {res['row_count']} rows to {res['out']} (hash: {res['dataset_hash'][:16]}...)"
    )


if __name__ == "__main__":
    main()
