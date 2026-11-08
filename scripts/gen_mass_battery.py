#!/usr/bin/env python3
"""Mass balanced twin battery (max-quality track): faults are abundant by design.

Generates a balanced episode set across families x rungs (+ clean) with fresh
IDs above the frozen/supplement ranges. Battery id: m0b-mass-balanced-v1.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

BATTERY_ID = "m0b-mass-balanced-v1"
MANIFEST_OUT = "docs/m0b_mass_manifest.json"
PARQUET_OUT = "artifacts/m0b_mass.parquet"
BASE_EP, BASE_CLEAN = 40000, 42000
FAMILIES = ("bias", "breakdown", "delay", "drift", "loss", "quality", "spike")
RUNGS = ("incipient", "caricature")


def build_specs(
    *, n_per_cell: int = 100, n_clean: int = 600, seed: int = 0
) -> tuple[list[int], list[int], dict[int, dict]]:
    """Deterministic spec grid: families x rungs fault episodes + clean episodes."""
    import numpy as np

    rng = np.random.default_rng(seed)
    faults: dict[int, dict] = {}
    fault_eps: list[int] = []
    k = 0
    for fam in FAMILIES:
        for rung in RUNGS:
            for j in range(n_per_cell):
                ep = BASE_EP + k
                k += 1
                mag = 0.5 if rung == "incipient" else 4.0
                # Twin rate budget: fault union <= 14 steps/ep (0.08*180).
                # Breakdown counts its EXTENDED window ceil(dur*mttr_mult), so it
                # uses short durs like the frozen battery (dur 4/7 + mttr_mult).
                extra: dict = {}
                if fam == "breakdown":
                    dur = int(rng.integers(4, 8))
                    extra = {"mttr_mult": float(rng.uniform(1.1, 1.6))}
                else:
                    dur = int(rng.integers(8, 13))
                faults[ep] = {
                    "class": fam,
                    "dur": dur,
                    "extra": extra,
                    "id": f"M-{fam[:2].upper()}{rung[0].upper()}{j:03d}",
                    "mag_rung": rung,
                    "mag_sigma": float(mag),
                    "origin": "A0",
                    "rep": False,
                    "sev": float(mag),
                    "t0": 150,
                }
                fault_eps.append(ep)
    clean_eps = [BASE_CLEAN + i for i in range(n_clean)]
    return fault_eps, clean_eps, faults


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="generate + export mass balanced battery")
    ap.add_argument("--n-per-cell", type=int, default=100)
    ap.add_argument("--n-clean", type=int, default=600)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--manifest", default=MANIFEST_OUT)
    ap.add_argument("--out", default=PARQUET_OUT)
    args = ap.parse_args(argv)
    from src import dataset_export

    fault_eps, clean_eps, faults = build_specs(
        n_per_cell=args.n_per_cell, n_clean=args.n_clean, seed=args.seed
    )
    res = dataset_export.export_v6(
        seeds=clean_eps + fault_eps,
        out=args.out,
        faults=faults,
        enable_natural_breakdown=False,
    )
    manifest = {
        "battery_id": BATTERY_ID,
        "fault_episodes": fault_eps,
        "clean_episodes": clean_eps,
        "rows": [faults[ep] for ep in fault_eps],
        "master_seed": args.seed,
    }
    p = pathlib.Path(args.manifest)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(
        f"mass {BATTERY_ID}: {len(fault_eps)} fault + {len(clean_eps)} clean -> {args.out}"
    )
    print(f"export: {res}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
