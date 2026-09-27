"""Deterministic replay CLI for twin simulation episodes.

FULLER replay CLI: seed + subgraph + version binding.
CLI:
    python -m src.replay --seed <int> --out <path> [--partition <name>] [--subgraph <spec>]
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from typing import Any

from src.config import CODE_VERSION, TWIN_SCHEMA
from src.twin import replay_digest, run_episode

# Keys excluded from canonical replay records per twin specification.
_WALLCLOCK_KEYS = frozenset({"wall_s", "timestamp", "clock", "elapsed"})
_DIGEST_SCRUB_FLOW_KEYS = frozenset({"starved_split"})

# Allowed plant partitions.
_VALID_PARTITIONS = frozenset({"line-A", "line-B", "line-C", "cell", "rework"})
_PARTITION_MAP = {
    "line-a": "line-A",
    "line-b": "line-B",
    "line-c": "line-C",
    "cell": "cell",
    "rework": "rework",
}


def _validate_seed(seed: Any) -> int:
    """Validate seed is a non-negative integer."""
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise ValueError(f"seed must be a non-negative int, got {seed!r}")
    return seed


def _validate_partition(partition: str | None) -> str | None:
    """Validate and normalize partition name if provided."""
    if partition is None:
        return None
    normalized = _PARTITION_MAP.get(partition.strip().lower())
    if normalized is None:
        raise ValueError(
            f"unknown partition {partition!r}, must be one of {sorted(_VALID_PARTITIONS)}"
        )
    return normalized


def _parse_subgraph(subgraph: Any) -> Any:
    """Parse subgraph spec if stringified JSON, otherwise return normalized value."""
    if subgraph is None:
        return None
    if isinstance(subgraph, str):
        trimmed = subgraph.strip()
        if not trimmed:
            raise ValueError("subgraph spec cannot be empty")
        try:
            parsed = json.loads(trimmed)
            if isinstance(parsed, (dict, list)):
                return parsed
        except (json.JSONDecodeError, TypeError):
            pass
        return trimmed
    return subgraph


def replay(
    seed: int,
    out: str | pathlib.Path,
    partition: str | None = None,
    subgraph: Any = None,
) -> dict[str, Any]:
    """Execute one simulation episode and write canonical JSONL with digest.

    Parameters:
        seed: Non-negative integer random seed.
        out: Target file path to write canonical JSONL record.
        partition: Optional partition name to record.
        subgraph: Optional subgraph specification to record.

    Returns:
        The written record dict including the computed replay digest.
    """
    valid_seed = _validate_seed(seed)
    valid_partition = _validate_partition(partition)
    valid_subgraph = _parse_subgraph(subgraph)

    # 1. Execute episode via twin.run_episode.
    raw_record = run_episode(seed=valid_seed, fault=None)

    # 2. Scrub wall-clock keys per twin._WALLCLOCK_KEYS.
    record: dict[str, Any] = {
        k: v for k, v in raw_record.items() if k not in _WALLCLOCK_KEYS
    }

    # 3. Scrub additive-only census flow keys per twin._DIGEST_SCRUB_FLOW_KEYS.
    flow_stats = record.get("flow_stats")
    if isinstance(flow_stats, dict) and any(
        k in flow_stats for k in _DIGEST_SCRUB_FLOW_KEYS
    ):
        record["flow_stats"] = {
            k: v for k, v in flow_stats.items() if k not in _DIGEST_SCRUB_FLOW_KEYS
        }

    # 4. Attach partition and subgraph if supplied.
    if valid_partition is not None:
        record["partition"] = valid_partition
    if valid_subgraph is not None:
        record["subgraph"] = valid_subgraph

    # 5. Ensure schema_version and code_version binding.
    record["schema_version"] = TWIN_SCHEMA
    record["code_version"] = CODE_VERSION

    # 6. Compute canonical digest over record BEFORE adding the digest key.
    record["digest"] = replay_digest(record)

    # 7. Write canonical JSONL to --out path (sorted keys, one line per record).
    out_path = pathlib.Path(out)
    if str(out).strip() == "":
        raise ValueError("output path cannot be empty")
    if out_path.is_dir():
        raise IsADirectoryError(f"output path is a directory: {out_path}")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(json.dumps(record, sort_keys=True, default=repr) + "\n")

    return record


def build_parser() -> argparse.ArgumentParser:
    """Build argument parser for CLI."""
    parser = argparse.ArgumentParser(
        prog="python -m src.replay",
        description="Deterministic replay CLI (FULLER replay: seed + subgraph + version binding).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        required=True,
        help="Episode seed (non-negative integer).",
    )
    parser.add_argument(
        "--out",
        type=str,
        required=True,
        help="Output path for canonical JSONL.",
    )
    parser.add_argument(
        "--partition",
        type=str,
        default=None,
        help="Optional partition name (line-A, line-B, line-C, cell, rework).",
    )
    parser.add_argument(
        "--subgraph",
        type=str,
        default=None,
        help="Optional subgraph specification.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Main CLI entrypoint."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.seed < 0:
        parser.error(f"seed must be a non-negative int, got {args.seed!r}")

    if not args.out or not args.out.strip():
        parser.error("output path cannot be empty")

    try:
        replay(
            seed=args.seed,
            out=args.out,
            partition=args.partition,
            subgraph=args.subgraph,
        )
    except (ValueError, TypeError, OSError, KeyError, RuntimeError) as exc:
        sys.stderr.write(f"replay error: {exc}\n")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
