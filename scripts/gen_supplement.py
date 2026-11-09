#!/usr/bin/env python3
"""Supplement battery (twin levers): long episodes + DR texture + doubles.

New battery ID m0b-mass-supplement-v1. Frozen manifests/parquets untouched.
Supplements, never replaces: frozen dense battery stays the reference.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

BATTERY_ID = "m0b-mass-supplement-v1"
BASE_SEED_EP = 60000
FAMILIES = ("bias", "breakdown", "delay", "drift", "loss", "quality", "spike")
RUNGS = ("incipient", "caricature")
GAP_BINS = ((0, 2), (3, 4), (5, 10), (11, 10**9))


def _mag(rung: str, rng: np.random.Generator) -> float:
    if rung == "incipient":
        return float(rng.uniform(1.0, 3.0))
    return float(rng.uniform(4.0, 7.0))


def _fault_dict(fam, rung, machine, t0, dur, mag, k, extra=None):
    return {
        "class": fam,
        "dur": dur,
        "extra": dict(extra or {}),
        "id": f"S-{fam[:2].upper()}{rung[0].upper()}{k:03d}",
        "mag_rung": rung,
        "mag_sigma": float(mag),
        "origin": str(machine),
        "rep": False,
        "sev": float(mag),
        "t0": int(t0),
    }


def build_supplement_specs(
    *,
    n_per_cell: int = 20,
    n_clean: int = 100,
    n_doubles: int = 60,
    episode_len: int = 1000,
    seed: int = 1,
    dr: bool = True,
) -> tuple[list[int], list[int], dict, dict, list[dict]]:
    """Spec grid: singles (family x rung) + pairwise doubles + clean.

    Returns (fault_eps, clean_eps, faults, textures, doubles_meta).
    Doubles cycle gap bins 0-2/3-4/5-10/>10 between the two onsets.
    """
    from src import config

    rng = np.random.default_rng(seed)
    machines = list(config.MACHINE_NAMES)
    faults: dict[int, object] = {}
    textures: dict[int, dict] = {}
    fault_eps: list[int] = []
    doubles_meta: list[dict] = []

    def tex():
        if not dr:
            return {"ar_coef": 0.6, "sine_amp": 0.5, "eps_scale": 0.5}
        return {
            "ar_coef": float(rng.uniform(0.2, 0.8)),
            "sine_amp": float(rng.uniform(0.0, 1.0)),
            "eps_scale": float(rng.uniform(0.3, 0.7)),
        }

    ep = BASE_SEED_EP
    k = 0
    for fam in FAMILIES:
        for rung in RUNGS:
            for _ in range(n_per_cell):
                dur = int(rng.integers(4, 8)) if fam == "breakdown" else int(rng.integers(8, 15))
                t0 = int(rng.integers(config.CAL_WIN, episode_len - dur - 5))
                m = str(rng.choice(machines))
                faults[ep] = _fault_dict(fam, rung, m, t0, dur, _mag(rung, rng), k)
                textures[ep] = tex()
                fault_eps.append(ep)
                ep += 1
                k += 1
    for i in range(n_doubles):
        lo, hi = GAP_BINS[i % len(GAP_BINS)]
        m1, m2 = rng.choice(machines, size=2, replace=False)
        f1, f2 = rng.choice(list(FAMILIES), size=2, replace=False)
        d1 = int(rng.integers(8, 15))
        t1 = int(rng.integers(config.CAL_WIN, episode_len - d1 - 30))
        gap = int(rng.integers(lo, min(hi, 60) + 1))
        d2 = int(rng.integers(8, 15))
        t2 = min(t1 + gap, episode_len - d2 - 5)
        f = [
            _fault_dict(f1, "caricature", str(m1), t1, d1, _mag("caricature", rng), k),
            _fault_dict(f2, "caricature", str(m2), t2, d2, _mag("caricature", rng), k + 1),
        ]
        faults[ep] = f
        textures[ep] = tex()
        fault_eps.append(ep)
        doubles_meta.append({"ep": ep, "gap": int(t2 - t1), "bin": [int(lo), int(hi)]})
        ep += 2
        k += 2
    clean_start = BASE_SEED_EP + len(fault_eps) + 1000
    clean_eps = [clean_start + i for i in range(n_clean)]
    assert not (set(fault_eps) & set(clean_eps))
    return fault_eps, clean_eps, faults, textures, doubles_meta


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="generate + export supplement battery")
    ap.add_argument("--n-per-cell", type=int, default=20)
    ap.add_argument("--n-clean", type=int, default=100)
    ap.add_argument("--n-doubles", type=int, default=60)
    ap.add_argument("--episode-len", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--manifest", default="docs/m0b_supplement_manifest.json")
    ap.add_argument("--out", default="artifacts/m0b_supplement.parquet")
    ap.add_argument("--shard-eps", type=int, default=100)
    ap.add_argument("--no-dr", action="store_true")
    args = ap.parse_args(argv)
    from src import dataset_export

    fault_eps, clean_eps, faults, textures, doubles = build_supplement_specs(
        n_per_cell=args.n_per_cell,
        n_clean=args.n_clean,
        n_doubles=args.n_doubles,
        episode_len=args.episode_len,
        seed=args.seed,
        dr=not args.no_dr,
    )
    all_eps = clean_eps + fault_eps
    shards = []
    out_base = pathlib.Path(args.out)
    for i in range(0, len(all_eps), args.shard_eps):
        shard_eps = all_eps[i : i + args.shard_eps]
        shard_out = str(out_base.with_name(f"{out_base.stem}_{i // args.shard_eps:02d}.parquet"))
        shard_faults = {ep: faults[ep] for ep in shard_eps if ep in faults}
        shard_tex = {ep: textures[ep] for ep in shard_eps if ep in textures}
        dataset_export.export_v6(
            seeds=shard_eps,
            out=shard_out,
            faults=shard_faults or None,
            texture=shard_tex or None,
            enable_natural_breakdown=False,
            episode_len=args.episode_len,
        )
        shards.append(shard_out)
    manifest = {
        "battery_id": BATTERY_ID,
        "episode_len": args.episode_len,
        "seed": args.seed,
        "n_fault": len(fault_eps),
        "n_clean": len(clean_eps),
        "n_doubles": len(doubles),
        "doubles": doubles,
        "dr": not args.no_dr,
        "shards": shards,
    }
    pathlib.Path(args.manifest).write_text(json.dumps(manifest, indent=2))
    print(f"battery {BATTERY_ID}: {len(fault_eps)} fault + {len(clean_eps)} clean -> {args.manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
