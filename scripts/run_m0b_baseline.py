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

from scripts.measure_cusum_p0 import H_CUSUM, P0_CUSUM, P1_CUSUM
from src import config, detect, gates, train_pipeline, twin

LAT_GATE = 3
# Bernoulli-CUSUM design: locked from clean-episode measurement (scripts/measure_cusum_p0.py).
CUSUM_H = H_CUSUM


def fit_run_only_thresholds(cal_seed: int, machine_names: list[str]) -> dict:
    """Quantile artifact fitted on all-RUN calibration steps only (state-aware fit)."""
    rec = twin.run_episode(cal_seed, None, enable_natural_breakdown=False)
    states = np.asarray(rec["states"])
    obs = np.asarray(rec["obs"], dtype=float).T
    mask = np.zeros_like(obs, dtype=bool)
    for j in range(len(machine_names)):
        for t in range(config.WARMUP_STEPS, config.CAL_WIN):
            mask[t, j] = states[j, t] == "RUN"
    return detect.fit_quantile_thresholds(obs, machine_names, clean_mask=mask)


def cusum_alarm_times(
    events: list[dict], p0: float, p1: float, h: float = CUSUM_H
) -> list[int]:
    """Event times where the Bernoulli CUSUM crosses h (quality expert)."""
    w_fail, w_pass = gates.bernoulli_cusum_weights(p0, p1)
    s = 0.0
    hits = []
    for t, passed in gates.kit_outcomes_from_events(events):
        s, alarm = gates.bernoulli_cusum_update(s, passed, w_fail, w_pass, h=h)
        if alarm:
            hits.append(int(t))
    return hits


def score_episode(
    rec: dict,
    fault: dict | None,
    thresholds: dict,
    machine_names: list[str],
    *,
    p0: float = P0_CUSUM,
    p1: float = P1_CUSUM,
    dump_path: str | None = None,
    clean_var: dict | None = None,
    fused_flags: np.ndarray | None = None,
) -> dict:
    """Score one episode: quantile OR structural gates OR quality CUSUM OR trained-ML flags.

    dump_path (optional .npz): persists max-machine quantile scores + full-length
    root-window labels for the threshold-free VUS-PR appendix.
    clean_var (optional): per-machine clean variance baselines for the quality
    variance gate; None disables it (legacy behavior).
    fused_flags (optional [T] bool): trained-ML per-step decisions ORed into yh/hit.

    tp/fp/fn vs root window; top-1/latency from quantile scores; hit if any
    expert fires at the origin inside [t0, t0+dur+LAT_GATE].
    """
    n = len(machine_names)
    obs = np.asarray(rec["obs"], dtype=float).T
    states = np.asarray(rec["states"])
    tput = np.asarray(rec["throughput"], dtype=float)
    states_tn = states.T
    suppress = states_tn == "DOWN"
    alarms_q, scores = detect.detect_exceedance(
        obs, thresholds, machine_names, suppress=suppress
    )
    if dump_path is not None:
        import numpy as _np

        lab = _np.zeros(config.T, dtype=int)
        if fault is not None:
            t0, dur = int(fault["t0"]), int(fault["dur"])
            lab[t0 : t0 + dur] = 1
        _np.savez_compressed(
            dump_path,
            scores=_np.asarray(scores, dtype=float).max(axis=1),
            labels=lab,
            fault_id="" if fault is None else str(fault.get("id", "")),
        )
    sigmas = [float(config.MACHINES[m]["sigma"]) for m in machine_names]
    counters = gates.track_counters(
        np.asarray(rec["obs"], dtype=float), states, tput, sigmas
    )
    gate = np.zeros_like(alarms_q)
    for j in range(n):
        if clean_var is not None and machine_names[j] in clean_var:
            gate[:, j] |= gates.variance_exceeds(
                obs[:, j], float(clean_var[machine_names[j]])
            )
        for t in range(config.T):
            st = str(states[j, t])
            if (
                gates.delay_gate(int(counters["tputlag"][j, t]), st)
                or gates.loss_gate(int(counters["stale"][j, t]))
                or gates.loss_combo_gate(
                    int(counters["tputlag"][j, t]), int(counters["stale"][j, t])
                )
                or gates.breakdown_gate(int(counters["downrun"][j, t]))
            ):
                gate[t, j] = True
    from src.fusion import episode_decision

    out: dict = {"tp": 0, "fp": 0, "fn": 0, "top": None, "latency": 999, "hit": False}
    if fused_flags is not None:
        _ml = np.asarray(fused_flags, dtype=bool).ravel()
        ml = np.zeros(config.T, dtype=bool)
        # OOF fused decisions exclude warmup steps; align to full-episode ticks.
        ml[config.T - len(_ml) :] = _ml[-min(len(_ml), config.T) :]
    else:
        ml = np.zeros(config.T, dtype=bool)
    cusum_hits = cusum_alarm_times(rec.get("events", []), p0, p1)
    cus = np.zeros(config.T, dtype=bool)
    for t in cusum_hits:
        if 0 <= int(t) < config.T:
            cus[int(t)] = True
    # Episode decision: dwell-confirmed screen OR debounced CUSUM (CUSUM has its
    # own hysteresis; dwelling it again would suppress legitimate single blips).
    yh_full = episode_decision(
        {
            "quantile": alarms_q.any(axis=1),
            "structural": gate.any(axis=1),
            "ml": ml,
        },
        k=3,
        window=5,
    ) | cus
    if fault is None:
        out["fp"] = int(yh_full[config.CAL_WIN :].sum())
        return out
    t0, dur = int(fault["t0"]), int(fault["dur"])
    origin = fault["origin"]
    j = machine_names.index(origin)
    scored = np.zeros(config.T - config.CAL_WIN, dtype=int)
    scored[t0 - config.CAL_WIN : t0 - config.CAL_WIN + dur] = 1
    yh = yh_full[config.CAL_WIN :].astype(int)
    q_alarm = bool(alarms_q[t0 : t0 + dur + LAT_GATE, j].any())
    g_alarm = bool(gate[t0 : t0 + dur + LAT_GATE, j].any())
    m_alarm = bool(ml[t0 : t0 + dur + LAT_GATE].any())
    c_alarm = any(t0 <= t < t0 + dur + LAT_GATE for t in cusum_hits)
    out["tp"] = int(((scored == 1) & (yh == 1)).sum())
    out["fp"] = int(((scored == 0) & (yh == 1)).sum())
    out["fn"] = int(((scored == 1) & (yh == 0)).sum())
    top, lat = detect.attribute_top1(scores, t0, dur, machine_names, lat_gate=LAT_GATE)
    out.update(
        fault_id=fault.get("id"),
        origin=origin,
        top=top,
        latency=lat,
        hit=bool(yh_full[t0 : t0 + dur + LAT_GATE].any()),
        experts={
            "quantile": q_alarm,
            "structural": g_alarm,
            "quality": c_alarm,
            "ml": m_alarm,
        },
    )
    return out


def run_battery(
    manifest: dict,
    thresholds: dict,
    machine_names: list[str],
    *,
    p0: float = P0_CUSUM,
    p1: float = P1_CUSUM,
    dump_dir: str | None = None,
    fused: dict | None = None,
) -> dict:
    """Run all manifest episodes + clean episodes; aggregate audit numbers.

    clean_var: per-machine clean variance baselines (quality gate); fused: optional
    dict episode-id -> [T] bool trained-ML decisions, ORed into the single decision.
    """
    clean_var = {m: float(thresholds[m].get("clean_var", 1.0)) for m in machine_names}
    rows = []
    for ep, row in zip(manifest["fault_episodes"], manifest["rows"]):
        rec = twin.run_episode(ep, dict(row), enable_natural_breakdown=False)
        dp = f"{dump_dir}/{row['id']}.npz" if dump_dir else None
        mf = (
            np.asarray(fused[row["id"]], dtype=bool)
            if fused and row["id"] in fused
            else None
        )
        rows.append(
            score_episode(
                rec,
                dict(row),
                thresholds,
                machine_names,
                p0=p0,
                p1=p1,
                dump_path=dp,
                clean_var=clean_var,
                fused_flags=mf,
            )
        )
    for ep in manifest["clean_episodes"]:
        rec = twin.run_episode(ep, None, enable_natural_breakdown=False)
        dp = f"{dump_dir}/clean_{ep}.npz" if dump_dir else None
        mf = (
            np.asarray(fused[f"clean_{ep}"], dtype=bool)
            if fused and f"clean_{ep}" in fused
            else None
        )
        rows.append(
            score_episode(
                rec,
                None,
                thresholds,
                machine_names,
                p0=p0,
                p1=p1,
                dump_path=dp,
                clean_var=clean_var,
                fused_flags=mf,
            )
        )
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
    expert_hits = {"quantile": 0, "structural": 0, "quality": 0}
    for r in lat_ok:
        for k, v in r.get("experts", {}).items():
            if v:
                expert_hits[k] = expert_hits.get(k, 0) + 1
    return {
        "f1_raw": train_pipeline.compute_raw_pointwise_f1(y_true, y_pred),
        "ac1": sum(1 for r in hits if r["top"] == r["origin"]) / len(hits),
        "mean_latency_hit": float(np.mean([r["latency"] for r in lat_ok]))
        if lat_ok
        else 999.0,
        "n_hit": len(lat_ok),
        "n_fault_episodes": len(hits),
        "clean_fp_total": sum(r["fp"] for r in rows if not r.get("fault_id")),
        "expert_hits": expert_hits,
        "misses": misses,
        "rows": [
            {
                **{
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
                },
                "experts": r.get("experts", {}),
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
    parser.add_argument("--dump-dir", default=None)
    parser.add_argument(
        "--fused",
        default=None,
        help="OOF fused-decisions parquet (episode_id + fused cols); ORed as 4th expert",
    )
    args = parser.parse_args(argv)

    start = time.perf_counter()
    manifest = json.loads(pathlib.Path(args.manifest).read_text(encoding="utf-8"))
    machines = list(config.MACHINE_NAMES)
    thresholds = fit_run_only_thresholds(args.cal_seed, machines)
    # Pass 1 (clean): sanity-check the locked p0 against this manifest; the lock wins.
    kits = fails = 0
    for ep in manifest["clean_episodes"]:
        rec = twin.run_episode(ep, None, enable_natural_breakdown=False)
        for _, passed in gates.kit_outcomes_from_events(rec.get("events", [])):
            kits += 1
            fails += 0 if passed else 1
    measured = fails / max(1, kits)
    if measured > 2 * P0_CUSUM:
        print(f"WARNING: clean fail rate {measured:.4f} > 2x locked p0 {P0_CUSUM:.4f}")
    if args.dump_dir:
        pathlib.Path(args.dump_dir).mkdir(parents=True, exist_ok=True)
    fused = None
    if args.fused:
        import pandas as _pd

        _df = _pd.read_parquet(args.fused)
        _by_ep = {
            str(k): np.asarray(g["fused"].to_numpy(dtype=bool))
            for k, g in _df.groupby(_df["episode_id"].astype(str))
        }
        _id_of = {
            str(ep): r["id"]
            for ep, r in zip(manifest["fault_episodes"], manifest["rows"])
        }
        fused = {}
        for ep_key, arr in _by_ep.items():
            if ep_key in _id_of:
                fused[_id_of[ep_key]] = arr
            else:
                fused[f"clean_{ep_key}"] = arr
    result = run_battery(
        manifest,
        thresholds,
        machines,
        p0=P0_CUSUM,
        p1=P1_CUSUM,
        dump_dir=args.dump_dir,
        fused=fused,
    )
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
