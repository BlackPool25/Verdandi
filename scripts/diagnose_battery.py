#!/usr/bin/env python3
"""Trigger-gated diagnosis battery: frozen w128-v2 detector + diagnose_from_trigger.

For each fault episode: score invariant w128 windows with the released
model, take first hot window at the locked global threshold as trigger,
run trigger-gated diagnosis, compare vs logged GT (root_id_step, t0,
sensor_vs_process, mag_rung). GT is eval-only, never an input.
"""

from __future__ import annotations

import argparse
import glob
import pathlib
import sys
from concurrent.futures import ProcessPoolExecutor

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd
from joblib import load

_WORKER: dict = {}


def _init_worker(artifact: str, thr_prop: float, wait: int) -> None:
    """Load the frozen model once per worker process (CPU fork-safe)."""
    from src.diagnose import confirm_trigger, diagnose_from_trigger
    from src.window_dataset import apply_norm, build_windows

    art = load(f"{artifact}/model.joblib")
    _WORKER["model"] = art["model"]
    _WORKER["w"] = int(art["w"])
    _WORKER["stride"] = int(art["stride"])
    _WORKER["med"] = np.asarray(art["norm_median"], dtype=float)
    _WORKER["iqr"] = np.asarray(art["norm_iqr"], dtype=float)
    _WORKER["n_obs"] = int(art["n_obs_features"])
    _WORKER["thr_prop"] = float(thr_prop)
    _WORKER["wait"] = int(wait)
    _WORKER["confirm_trigger"] = confirm_trigger
    _WORKER["diagnose_from_trigger"] = diagnose_from_trigger
    _WORKER["apply_norm"] = apply_norm
    _WORKER["build_windows"] = build_windows


def _work_episode(job: tuple) -> tuple:
    """Full per-episode pipeline: windows -> score -> confirm -> diagnose.

    Runs in a worker process (or serially). Deterministic: no shared state,
    order preserved by the caller's map.
    """
    g, obs, meta = job
    model, w, stride = _WORKER["model"], _WORKER["w"], _WORKER["stride"]
    med, iqr, n_obs = _WORKER["med"], _WORKER["iqr"], _WORKER["n_obs"]
    thr_prop, wait = _WORKER["thr_prop"], _WORKER["wait"]
    confirm_trigger = _WORKER["confirm_trigger"]
    diagnose_from_trigger = _WORKER["diagnose_from_trigger"]
    apply_norm, build_windows = _WORKER["apply_norm"], _WORKER["build_windows"]
    fam, rung, root, true_sp, true_t0 = meta
    X, _, _, _, starts = build_windows(g, w=w, stride=stride, invariant=True, return_starts=True)
    s = np.asarray(model.predict_proba(apply_norm(X, med, iqr, n_obs))[:, 1])
    trig = confirm_trigger(s, starts, thr_prop, m=2, n=3)
    if trig is None:
        return (fam, rung, root, None, None, None, False, "unconfirmed")
    anchor = trig + wait
    back = 64 + wait
    m_idx = (starts >= anchor - back) & (starts <= anchor + 150)
    if not m_idx.any():
        return (fam, rung, root, None, None, None, True, "no-window")
    if float(s[m_idx].max()) < 0.9:
        return (fam, rung, root, None, None, None, True, "low-confidence")
    try:
        out = diagnose_from_trigger(g, obs, anchor, back=back)
    except Exception:  # noqa: BLE001 - harness records failures as rows
        return (fam, rung, root, None, None, None, True, "error")
    if not out:
        return (fam, rung, root, None, None, None, True, "empty")
    f0 = out[0]
    struct_process = f0["onset_kind"] == "counter" or (
        f0["onset_kind"] == "state" and f0["own_state"] in ("DOWN", "BLOCKED")
    )
    pred_sp = "process" if struct_process else "sensor"
    return (
        fam,
        rung,
        root,
        f0["machine"],
        f0["onset"] - true_t0,
        pred_sp == true_sp,
        True,
        "diagnosed",
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="trigger-gated diagnosis battery")
    ap.add_argument("--artifact", default="artifacts/window-gbm-w128-v2")
    ap.add_argument("--glob", default="artifacts/m0b_mass_*.parquet")
    ap.add_argument("--max-eps", type=int, default=110)
    ap.add_argument("--thr", type=float, default=0.8)
    ap.add_argument(
        "--rung", default="", help="filter to mag_rung (incipient/caricature)"
    )
    ap.add_argument(
        "--wait",
        type=int,
        default=32,
        help="wait budget W in ticks after confirm; anchor=trig+W, past covers W+64 back",
    )
    ap.add_argument("--n-jobs", type=int, default=1, help="worker processes (model loads once per worker)")
    args = ap.parse_args(argv)

    try:
        import json

        with open(f"{args.artifact}/thresholds.json") as fh:
            fam_thr = json.load(fh)
        thr_prop = min(float(v) for k, v in fam_thr.items() if k != "none")
    except OSError:
        thr_prop = 0.5

    rows: list = []
    jobs: list = []
    for p in sorted(glob.glob(args.glob)):
        df = pd.read_parquet(p)
        if df["y"].sum() == 0:
            continue
        obs = [c for c in df.columns if c.startswith("obs_")]
        for fe in list(df[df.y == 1]["episode_id"].unique()):
            if len(jobs) >= args.max_eps:
                break
            g = df[df.episode_id == fe].sort_values("step").reset_index(drop=True)
            r = g[g.y == 1].iloc[0]
            if args.rung and str(r["mag_rung"]) != args.rung:
                continue
            meta = (
                str(r["fault_family"]),
                str(r["mag_rung"]),
                str(r["root_id_step"]),
                str(r["sensor_vs_process"]),
                int(g[g.y == 1]["step"].min()),
            )
            jobs.append((g, obs, meta))
        if len(jobs) >= args.max_eps:
            break

    if args.n_jobs == 1:
        _init_worker(args.artifact, thr_prop, args.wait)
        done = [_work_episode(j) for j in jobs]
    else:
        # Forked processes: private globals per worker, model loads once.
        # build_windows is GIL-bound pandas, so threads give no speedup.
        with ProcessPoolExecutor(
            max_workers=args.n_jobs,
            initializer=_init_worker,
            initargs=(args.artifact, thr_prop, args.wait),
        ) as ex:
            done = list(ex.map(_work_episode, jobs))
    rows.extend(done)
    n_trig = sum(1 for r in rows if r[7] in ("diagnosed", "error", "empty"))

    print(f"n={len(rows)} trigger_rate={n_trig / max(1, len(rows)):.3f} (MEASURED)")
    hit = [r for r in rows if r[3] is not None]
    print(
        f"top1={sum(1 for r in hit if r[2] == r[3]) / max(1, len(hit)):.3f} (MEASURED, n={len(hit)})"
    )
    errs = [abs(r[4]) for r in hit if r[4] is not None]
    if errs:
        print(
            f"onset med={float(np.median(errs)):.1f} p90={float(np.quantile(errs, 0.9)):.1f} (MEASURED)"
        )
    print(f"coord_acc={sum(1 for r in hit if r[5]) / max(1, len(hit)):.3f} (MEASURED)")
    import collections

    print("gates:", dict(collections.Counter(r[7] for r in rows)))
    for rung in ("incipient", "caricature"):
        sub = [r for r in rows if r[1] == rung and r[3] is not None]
        e = [abs(r[4]) for r in sub if r[4] is not None]
        print(
            f"{rung} n={len(sub)} top1={sum(1 for r in sub if r[2] == r[3]) / max(1, len(sub)):.3f} "
            f"mederr={float(np.median(e)):.1f} (MEASURED)"
            if e
            else f"{rung} n={len(sub)} empty"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
