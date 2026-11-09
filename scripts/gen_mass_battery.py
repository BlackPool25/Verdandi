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
BASE_SEED_EP = 40000
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
    # Fault IDs come first; clean IDs start past the whole fault block — no
    # overlap, ever (at n_per_cell=100 the ranges happened to miss; at 300
    # the clean block landed inside the fault block and 200 clean episodes
    # silently became faults).
    n_fault = len(FAMILIES) * len(RUNGS) * n_per_cell
    base_fault, base_clean = BASE_SEED_EP, BASE_SEED_EP + n_fault + 1000
    # Faults strike any machine at any valid onset (uniform over machines and
    # the feasible onset window). A single origin/onset teaches the model one
    # machine's baselines — and invites memorizing (machine, time) instead of
    # the signature. Window features carry no absolute clock, so time cannot
    # leak; machine identity can, and is tested by leave-machine-out.
    from src import config

    machines = list(config.MACHINE_NAMES)
    for fam in FAMILIES:
        for rung in RUNGS:
            for j in range(n_per_cell):
                ep = base_fault + k
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
                    "origin": str(rng.choice(machines)),
                    "rep": False,
                    "sev": float(mag),
                    "t0": int(rng.integers(config.CAL_WIN, config.T - dur - 5)),
                }
                fault_eps.append(ep)
    clean_eps = [base_clean + i for i in range(n_clean)]
    assert not (set(fault_eps) & set(clean_eps)), "fault/clean episode ID collision"
    return fault_eps, clean_eps, faults


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="generate + export mass balanced battery")
    ap.add_argument("--n-per-cell", type=int, default=100)
    ap.add_argument("--n-clean", type=int, default=600)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--manifest", default=MANIFEST_OUT)
    ap.add_argument("--out", default=PARQUET_OUT)
    ap.add_argument("--shard-eps", type=int, default=400)
    args = ap.parse_args(argv)
    from src import dataset_export

    fault_eps, clean_eps, faults = build_specs(
        n_per_cell=args.n_per_cell, n_clean=args.n_clean, seed=args.seed
    )
    # Shard the export: each shard stays under the 100MB export size cap.
    all_eps = clean_eps + fault_eps
    shards = []
    out_base = pathlib.Path(args.out)
    for i in range(0, len(all_eps), args.shard_eps):
        shard_eps = all_eps[i : i + args.shard_eps]
        shard_out = str(
            out_base.with_name(f"{out_base.stem}_{i // args.shard_eps:02d}.parquet")
        )
        shard_faults = {ep: faults[ep] for ep in shard_eps if ep in faults}
        dataset_export.export_v6(
            seeds=shard_eps,
            out=shard_out,
            # Empty dict trips export's int-key lookup ({} is not None) — pass None.
            faults=shard_faults or None,
            enable_natural_breakdown=False,
        )
        shards.append(shard_out)
    manifest = {
        "battery_id": BATTERY_ID,
        "fault_episodes": fault_eps,
        "clean_episodes": clean_eps,
        "rows": [faults[ep] for ep in fault_eps],
        "master_seed": args.seed,
        "shards": shards,
    }
    p = pathlib.Path(args.manifest)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(
        f"mass {BATTERY_ID}: {len(fault_eps)} fault + {len(clean_eps)} clean"
        f" -> {len(shards)} shards"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
