#!/usr/bin/env python3
"""Measure clean per-kit flag rate p0 and lock Bernoulli-CUSUM (p1, h).

Battery-realistic invocation: clean manifest episodes, natural breakdowns off
(exactly as run_m0b_baseline.run_battery invokes them). If Task 9 enables
naturals as a tagged stratum, re-run this script and re-lock.
Locked 2026-11-08: measured on clean eps 30201-30210 (see main output below).
"""

from __future__ import annotations

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import numpy as np

from src import gates, twin

CLEAN_SEEDS = list(range(30201, 30211))

# Locked constants (measured 2026-11-08: 0/400 failed kits on clean eps 30201-30210,
# battery-realistic invocation. p0 uses Laplace smoothing (fails+1)/(total+2):
# a zero numerator must not zero the weights (log(0)) nor pretend perfection;
# 1/402 ~= 0.00249, i.e. the clean-fail rate is bounded, not known. Upper 95%
# bound by rule-of-three ~= 0.0075. Re-lock if naturals join the battery.
P0_CUSUM = 1 / 402
P1_CUSUM = 0.25
H_CUSUM = 3.0


def measure_p0(seeds: list[int]) -> dict:
    """Per-kit fail rate over clean episodes: fails / total kits."""
    fails = total = 0
    per_ep = []
    for seed in seeds:
        rec = twin.run_episode(seed, None, enable_natural_breakdown=False)
        outcomes = gates.kit_outcomes_from_events(rec.get("events", []))
        f = sum(1 for _, passed in outcomes if not passed)
        fails += f
        total += len(outcomes)
        per_ep.append((seed, f, len(outcomes)))
    return {
        "p0": fails / total if total else 0.0,
        "fails": fails,
        "total": total,
        "per_episode": per_ep,
    }


def arl_table(p0: float, p1: float, hs=(2.0, 3.0, 4.0, 5.0), seed: int = 0) -> dict:
    """In-control ARL0 (false-alarm kits) and out-of-control ARL1 per h."""
    rng = np.random.default_rng(seed)
    w_fail, w_pass = gates.bernoulli_cusum_weights(p0, p1)
    out = {}
    for h in hs:
        for p, key in ((p0, "arl0"), (p1, "arl1")):
            rl = []
            for _ in range(2000):
                s, t = 0.0, 0
                while True:
                    t += 1
                    s, alarm = gates.bernoulli_cusum_update(
                        s, bool(rng.random() >= p), w_fail, w_pass, h=h
                    )
                    if alarm:
                        break
                rl.append(t)
            out[(h, key)] = float(np.mean(rl))
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.parse_args(argv)
    m = measure_p0(CLEAN_SEEDS)
    print(f"p0={m['p0']:.4f} ({m['fails']}/{m['total']} failed kits)")
    for seed, f, t in m["per_episode"]:
        print(f"  ep {seed}: {f}/{t}")
    p0 = max(m["p0"], 1e-3)
    for h in (2.0, 3.0, 4.0, 5.0):
        t = arl_table(p0, P1_CUSUM, hs=(h,))
        print(f"  h={h}: ARL0={t[(h, 'arl0')]:.0f} kits ARL1={t[(h, 'arl1')]:.1f} kits")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
