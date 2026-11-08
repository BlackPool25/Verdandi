#!/usr/bin/env python3
"""Export the frozen-182 battery as schema-v6 parquet for the trained pool.

Battery-realistic invocation: natural breakdowns OFF (exactly as
run_m0b_baseline.run_battery invokes the twin). Re-export with naturals when
the battery enables the tagged natural stratum.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import pandas as pd  # type: ignore[import-untyped]

from src import dataset_export

MANIFEST = "docs/m0b_battery_manifest.json"
DEFAULT_OUT = "artifacts/m0b_v6.parquet"


def manifest_faults(manifest: dict) -> dict[int, dict]:
    """{episode_seed: fault spec} aligned with fault_episodes order."""
    return {
        ep: dict(row) for ep, row in zip(manifest["fault_episodes"], manifest["rows"])
    }


def export_subset(clean_seed: int, fault_id: str, out: str) -> pd.DataFrame:
    """Export 1 clean + 1 fault episode (fast contract probe)."""
    manifest = json.loads(pathlib.Path(MANIFEST).read_text(encoding="utf-8"))
    by_id = {
        r["id"]: (ep, r) for ep, r in zip(manifest["fault_episodes"], manifest["rows"])
    }
    ep, row = by_id[fault_id]
    res = dataset_export.export_v6(
        seeds=[clean_seed, ep],
        out=out,
        faults={ep: dict(row)},
        enable_natural_breakdown=False,
    )
    return dataset_export.load_v6_dataset(res["out"])


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="export frozen-182 v6 battery parquet")
    ap.add_argument("--manifest", default=MANIFEST)
    ap.add_argument("--out", default=DEFAULT_OUT)
    args = ap.parse_args(argv)
    manifest = json.loads(pathlib.Path(args.manifest).read_text(encoding="utf-8"))
    res = dataset_export.export_v6(
        seeds=manifest["clean_episodes"] + manifest["fault_episodes"],
        out=args.out,
        faults=manifest_faults(manifest),
        enable_natural_breakdown=False,
    )
    df = dataset_export.load_v6_dataset(res["out"])
    print(f"episodes={df['episode_id'].nunique()} rows={len(df)} -> {res['out']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
