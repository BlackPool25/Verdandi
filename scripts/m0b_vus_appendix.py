#!/usr/bin/env python3
"""Per-family VUS-PR appendix + hit-rate adjudication for the M0b-T battery.

Reads score dumps (--dump-dir of run_m0b_baseline), the frozen manifest, and
the baseline audit JSON; writes an appendix JSON with per-family VUS-PR
(quantile expert, threshold-free primary), hit rate + Wilson 95% CI, and the
CUSUM-only clean-hit rate (quality-expert false-alarm visibility gap).
"""

from __future__ import annotations

import argparse
import json
import math
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import numpy as np

from src import gates, twin
from src.vus_pr import vus_pr


def wilson(x: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson 95% interval for a binomial rate."""
    if n == 0:
        return (float("nan"), float("nan"))
    p = x / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - m) / d, (c + m) / d)


def build_appendix(dump_dir: str, families: dict[str, str]) -> dict:
    """Per-family VUS-PR over fault-episode score dumps (clean eps excluded)."""
    per_fam: dict[str, list[float]] = {}
    for name, fam in families.items():
        z = np.load(pathlib.Path(dump_dir) / f"{name}.npz")
        v = vus_pr(z["scores"], z["labels"])
        if np.isfinite(v):
            per_fam.setdefault(fam, []).append(float(v))
    return {
        fam: {
            "n": len(v),
            "vus_pr_mean": float(np.mean(v)),
            "vus_pr_min": float(np.min(v)),
        }
        for fam, v in sorted(per_fam.items())
    }


def cusum_clean_hit_rate(clean_eps: list[int], p0: float, p1: float, h: float) -> dict:
    """Fraction of clean episodes where the locked CUSUM fires at least once."""
    hits = 0
    for ep in clean_eps:
        rec = twin.run_episode(ep, None, enable_natural_breakdown=False)
        w_fail, w_pass = gates.bernoulli_cusum_weights(p0, p1)
        s = 0.0
        for _, passed in gates.kit_outcomes_from_events(rec.get("events", [])):
            s, alarm = gates.bernoulli_cusum_update(s, passed, w_fail, w_pass, h=h)
            if alarm:
                hits += 1
                break
    return {
        "n_clean": len(clean_eps),
        "cusum_clean_hit": hits,
        "rate": hits / len(clean_eps) if clean_eps else 0.0,
    }


def main(argv: list[str] | None = None) -> int:
    from scripts.measure_cusum_p0 import H_CUSUM, P0_CUSUM, P1_CUSUM

    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default="docs/m0b_battery_manifest.json")
    ap.add_argument("--baseline", default="artifacts/m0b_baseline.json")
    ap.add_argument("--dump-dir", default="artifacts/m0b_scores")
    ap.add_argument("--out", default="artifacts/m0b_vus_appendix.json")
    args = ap.parse_args(argv)

    manifest = json.loads(pathlib.Path(args.manifest).read_text(encoding="utf-8"))
    baseline = json.loads(pathlib.Path(args.baseline).read_text(encoding="utf-8"))
    families = {r["id"]: r["class"] for r in manifest["rows"]}
    appendix = build_appendix(args.dump_dir, families)
    for fam, rows in _family_rows(manifest, baseline).items():
        hits = sum(1 for r in rows if r["hit"])
        lo, hi = wilson(hits, len(rows))
        appendix.setdefault(fam, {}).update(
            {
                "hit_rate": hits / len(rows),
                "hit_wilson95": [lo, hi],
                "n_hit": hits,
                "n_episodes": len(rows),
            }
        )
    appendix["_cusum_clean"] = cusum_clean_hit_rate(
        manifest["clean_episodes"], P0_CUSUM, P1_CUSUM, H_CUSUM
    )
    appendix["_bars"] = {
        "f1_raw": baseline["f1_raw"],
        "ac1": baseline["ac1"],
        "clean_fp_total": baseline["clean_fp_total"],
    }
    pathlib.Path(args.out).write_text(json.dumps(appendix, indent=2), encoding="utf-8")
    for fam, a in sorted(appendix.items()):
        if fam.startswith("_"):
            continue
        print(
            f"{fam:10s} n={a.get('n_episodes', a.get('n')):3d} "
            f"VUS-PR={a.get('vus_pr_mean', float('nan')):.3f} "
            f"hit={a.get('hit_rate', float('nan')):.2f}"
        )
    print("cusum-clean:", appendix["_cusum_clean"])
    return 0


def _family_rows(manifest: dict, baseline: dict) -> dict[str, list[dict]]:
    fam_of = {r["id"]: r["class"] for r in manifest["rows"]}
    out: dict[str, list[dict]] = {}
    for r in baseline["rows"]:
        out.setdefault(fam_of[r["fault_id"]], []).append(r)
    return out


if __name__ == "__main__":
    raise SystemExit(main())
