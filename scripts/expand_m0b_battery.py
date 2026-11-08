#!/usr/bin/env python3
"""Twin supplement for weak families (Task 26): delay/loss/quality expansion.

Frozen-182 manifest is NEVER modified; this writes a NEW supplement manifest
(battery id m0b-train-supplement-v1) with fresh seeds above the frozen range.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

BATTERY_ID = "m0b-train-supplement-v1"
SUPPLEMENT_OUT = "docs/m0b_battery_supplement.json"
FROZEN_MANIFEST = "docs/m0b_battery_manifest.json"

FAMILIES = ("delay", "loss", "quality")
RUNGS = ("incipient", "caricature")


def build_supplement(out: str, *, n_per_family: int = 4, seed: int = 0) -> dict:
    """Build supplement manifest dict + write to out (deterministic on seed)."""
    import numpy as np

    frozen = json.loads(pathlib.Path(FROZEN_MANIFEST).read_text(encoding="utf-8"))
    used_eps = set(frozen["fault_episodes"]) | set(frozen["clean_episodes"])
    rng = np.random.default_rng(seed)
    base_fault, base_clean = 31000, 31200
    fault_eps: list[int] = []
    clean_eps = [base_clean + i for i in range(4)]
    rows: list[dict] = []
    k = 0
    for fam in FAMILIES:
        for j in range(n_per_family):
            rung = RUNGS[(j + int(rng.integers(0, 2))) % 2]
            ep = base_fault + k
            while ep in used_eps:
                ep += 1
            k += 1
            mag = 0.5 if rung == "incipient" else 4.0
            rows.append(
                {
                    "class": fam,
                    "dur": int(rng.integers(8, 15)),
                    "extra": {},
                    "id": f"S-{fam[:2].upper()}{j:02d}",
                    "mag_rung": rung,
                    "mag_sigma": float(mag),
                    "origin": "A0",
                    "rep": False,
                    "sev": float(mag),
                    "t0": 150,
                }
            )
            fault_eps.append(ep)
    m = {
        "battery_id": BATTERY_ID,
        "fault_episodes": fault_eps,
        "clean_episodes": clean_eps,
        "rows": rows,
        "master_seed": seed,
    }
    p = pathlib.Path(out)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(m, indent=2), encoding="utf-8")
    return m


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="build weak-family supplement manifest")
    ap.add_argument("--out", default=SUPPLEMENT_OUT)
    ap.add_argument("--n-per-family", type=int, default=4)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args(argv)
    m = build_supplement(args.out, n_per_family=args.n_per_family, seed=args.seed)
    print(
        f"supplement {BATTERY_ID}: {len(m['fault_episodes'])} fault + {len(m['clean_episodes'])} clean -> {args.out}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
