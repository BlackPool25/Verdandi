#!/usr/bin/env python3
"""M0b quantile baseline audit (detector half of OQ-2 + Phase-1 re-baseline).

Runs the frozen manifest through the quantile/IQR artifact detector:
raw point-wise F1 (PA-off, any-machine alarm vs root window), AC@1 via
attribute_top1, latency, and the miss list feeding the safety taxonomy.
Flip% needs the PCMCI graph (walk/pcmci_job) — explicitly out of scope here.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import numpy as np

from src import config, detect, train_pipeline, twin

LAT_GATE = 3


def score_episode(
    rec: dict,
    fault: dict | None,
    thresholds: dict,
    machine_names: list[str],
) -> dict:
    """Score one episode: tp/fp/fn vs root window, top-1, latency, hit."""
    obs = np.asarray(rec["obs"], dtype=float).T
    alarms, scores = detect.detect_exceedance(obs, thresholds, machine_names)
    out: dict = {"tp": 0, "fp": 0, "fn": 0, "top": None, "latency": 999, "hit": False}
    if fault is None:
        out["fp"] = int(alarms[config.CAL_WIN :].sum())
        return out
    t0, dur = int(fault["t0"]), int(fault["dur"])
    origin = fault["origin"]
    j = machine_names.index(origin)
    scored = np.zeros(config.T - config.CAL_WIN, dtype=int)
    scored[t0 - config.CAL_WIN : t0 - config.CAL_WIN + dur] = 1
    yh = alarms[config.CAL_WIN :, :].max(axis=1).astype(int)
    out["tp"] = int(((scored == 1) & (yh == 1)).sum())
    out["fp"] = int(((scored == 0) & (yh == 1)).sum())
    out["fn"] = int(((scored == 1) & (yh == 0)).sum())
    top, lat = detect.attribute_top1(scores, t0, dur, machine_names, lat_gate=LAT_GATE)
    out.update(
        fault_id=fault.get("id"),
        origin=origin,
        top=top,
        latency=lat,
        hit=bool(alarms[t0 : t0 + dur + LAT_GATE, j].any()),
    )
    return out


def run_battery(manifest: dict, thresholds: dict, machine_names: list[str]) -> dict:
    """Run all manifest episodes + clean episodes; aggregate audit numbers."""
    rows = []
    for ep, row in zip(manifest["fault_episodes"], manifest["rows"]):
        rec = twin.run_episode(ep, dict(row))
        rows.append(score_episode(rec, dict(row), thresholds, machine_names))
    for ep in manifest["clean_episodes"]:
        rec = twin.run_episode(ep, None)
        rows.append(score_episode(rec, None, thresholds, machine_names))
    tp = sum(r["tp"] for r in rows)
    fp = sum(r["fp"] for r in rows)
    fn = sum(r["fn"] for r in rows)
    y_true = np.array([1] * (tp + fn) + [0] * fp)
    y_pred = np.array([1] * tp + [0] * fn + [1] * fp)
    hits = [r for r in rows if r.get("fault_id")]
    lat_ok = [r for r in hits if r["hit"]]
    misses = [
        {"id": r["fault_id"], "origin": r["origin"], "latency": r["latency"]}
        for r in hits
        if not r["hit"]
    ]
    return {
        "f1_raw": train_pipeline.compute_raw_pointwise_f1(y_true, y_pred),
        "ac1": sum(1 for r in hits if r["top"] == r["origin"]) / len(hits),
        "mean_latency_hit": float(np.mean([r["latency"] for r in lat_ok]))
        if lat_ok
        else 999.0,
        "n_hit": len(lat_ok),
        "n_fault_episodes": len(hits),
        "clean_fp_total": sum(r["fp"] for r in rows if not r.get("fault_id")),
        "misses": misses,
        "rows": [
            {
                k: r[k]
                for k in (
                    "fault_id",
                    "origin",
                    "top",
                    "latency",
                    "hit",
                    "tp",
                    "fp",
                    "fn",
                )
            }
            for r in hits
        ],
    }


def main(argv: list[str] | None = None) -> int:
    """CLI: fit artifact on cal seed 7, run battery, write audit JSON."""
    parser = argparse.ArgumentParser(description="M0b quantile baseline audit")
    parser.add_argument("--out", default="artifacts/m0b_baseline.json")
    parser.add_argument("--manifest", default="docs/m0b_battery_manifest.json")
    parser.add_argument("--cal-seed", type=int, default=7)
    args = parser.parse_args(argv)

    start = time.perf_counter()
    manifest = json.loads(pathlib.Path(args.manifest).read_text(encoding="utf-8"))
    machines = list(config.MACHINE_NAMES)
    thresholds = detect.fit_quantile_thresholds(
        twin.run_calibration(args.cal_seed), machines
    )
    result = run_battery(manifest, thresholds, machines)
    result["wall_seconds"] = time.perf_counter() - start
    result["cal_seed"] = args.cal_seed
    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, default=float), encoding="utf-8")
    print(
        f"F1={result['f1_raw']:.3f} AC@1={result['ac1']:.3f} "
        f"hit={result['n_hit']}/{result['n_fault_episodes']} "
        f"misses={len(result['misses'])} wall={result['wall_seconds']:.1f}s"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
