"""Plumbing audit CLI: 5x2 family x rung reachability matrix."""

from __future__ import annotations

MATRIX: list[tuple[str, str]] = [
    (fam, rung)
    for fam in ("loss", "quality", "drift", "bias", "spike")
    for rung in ("caricature", "incipient")
]

_ORIGIN = {"loss": "B2", "quality": "C7", "drift": "A2", "bias": "C1", "spike": "B8"}
_MAG = {"caricature": 5.0, "incipient": 2.0}
_DUR = {"loss": 60, "quality": 45, "drift": 90, "bias": 60, "spike": 8}


def _fault(fam: str, rung: str, seed: int) -> dict:
    return {
        "origin": _ORIGIN[fam],
        "class": fam,
        "t0": 150,
        "dur": _DUR[fam],
        "mag_sigma": _MAG[rung],
    }


def main(argv: list[str] | None = None) -> int:
    import argparse

    from src.plumbing import CARRIERS, paired_z

    ap = argparse.ArgumentParser(description="plumbing reachability audit")
    ap.add_argument("--k", type=float, default=3.0)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args(argv)
    fails = 0
    print(f"{'family':<9}{'rung':<11}{'fired':<7}{'tick':<6}carrier")
    for fam, rung in MATRIX:
        out = paired_z(_fault(fam, rung, args.seed), args.seed, CARRIERS[fam], args.k)
        tick = "" if out["tick"] is None else str(out["tick"])
        best = ""
        if out["per_carrier"]:
            c, (z, _) = max(out["per_carrier"].items(), key=lambda kv: kv[1][0])
            best = f"{c}={z:.1f}"
        print(f"{fam:<9}{rung:<11}{str(out['fired']):<7}{tick:<6}{best}")
        fails += not out["fired"]
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
