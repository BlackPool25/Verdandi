#!/usr/bin/env python3
"""Onset-localization error vs window-center heuristic on the dense battery.

For each fault episode: trigger = first tuned-decision window (w128 OOF);
baseline onset = window center; localizer onset = family-routed tick
estimator (counter edge / CUSUM backtrack / EWMA) on raw tick signals.
Reports median |est - t0| per family for both. Falsifiable bar: localizer
median <= 6 ticks on obs families, <= 4 on structural, with no recall change
(triggers are untouched — this only re-times them).
"""

from __future__ import annotations

import argparse
import glob
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd  # type: ignore[import-untyped]

STRUCT_COUNTER = {"delay": "cycle_lag", "loss": "stale_hold_run", "breakdown": "down_run"}

NEED_COLS = ["episode_id", "step"]


def _eval_one(ep, g, ow, r, obs_cols):
    """Onset errors for one episode; pure function (parallel-safe)."""
    from src.localize import counter_edge, cusum_backtrack, ewma_onset

    fam, t0 = r["class"], int(r["t0"])
    starts = np.arange(0, len(g) - 128 + 1, 8)[: len(ow)]
    hot = np.flatnonzero(
        (ow["score"].to_numpy(dtype=float) >= 0.8) & (starts >= t0 - 128)
    )
    if not len(hot):
        return None
    trig = int(starts[hot[0]])
    base = trig + 64
    proj = np.abs(
        g[obs_cols].to_numpy(dtype=float)
        - np.median(g[obs_cols].to_numpy(dtype=float), axis=0)
    ).max(axis=1)
    if fam in STRUCT_COUNTER and STRUCT_COUNTER[fam] in g:
        est = counter_edge(g[STRUCT_COUNTER[fam]].to_numpy(), trig)
    elif fam == "drift":
        est = ewma_onset(proj, trig)
    else:
        est = cusum_backtrack(proj, trig)
    if est is None:
        return None
    return (fam, float(abs(base - t0)), float(abs(est - t0)))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="localization error vs heuristic")
    ap.add_argument("--oof", required=True)
    ap.add_argument("--parquet", default="artifacts/m0b_mass_*.parquet")
    ap.add_argument("--manifest", default="docs/m0b_mass_manifest.json")
    ap.add_argument("--max-eps", type=int, default=0)
    ap.add_argument("--n-jobs", type=int, default=-1)
    args = ap.parse_args(argv)

    from joblib import Parallel, delayed  # type: ignore[import-untyped]

    oof = pd.read_parquet(args.oof)
    keep = ["episode_id", "step", "cycle_lag", "stale_hold_run", "down_run"]
    paths = sorted(glob.glob(args.parquet))
    first = pd.read_parquet(paths[0])
    obs_cols = [c for c in first.columns if c.startswith("obs_")]
    df = pd.concat(
        [pd.read_parquet(p, columns=keep + obs_cols) for p in paths],
        ignore_index=True,
    )
    m = json.loads(pathlib.Path(args.manifest).read_text(encoding="utf-8"))
    info = {e: r for e, r in zip(m["fault_episodes"], m["rows"])}
    # Single groupby pass: no per-episode full-frame scans.
    frames = {ep: g.sort_values("step") for ep, g in df.groupby("episode_id", sort=False)}
    oofs = {ep: g for ep, g in oof.groupby("ep", sort=False)}

    errs_base: dict[str, list[float]] = {}
    errs_loc: dict[str, list[float]] = {}
    eps = sorted(oof["ep"].unique())
    if args.max_eps:
        eps = eps[: args.max_eps]
    tasks = [(ep, frames[int(ep)], oofs[ep], info[int(ep)], obs_cols)
             for ep in eps if int(ep) in info and int(ep) in frames]
    for res in Parallel(n_jobs=args.n_jobs)(
        delayed(_eval_one)(*t) for t in tasks
    ):
        if res is None:
            continue
        fam, b, v = res
        errs_base.setdefault(fam, []).append(b)
        errs_loc.setdefault(fam, []).append(v)
    for fam in sorted(set(errs_base) | set(errs_loc)):
        b = np.asarray(errs_base.get(fam, [float("nan")]), dtype=float)
        v = np.asarray(errs_loc.get(fam, [float("nan")]), dtype=float)
        print(
            f"{fam:10s} n={len(v):4d} base_med={float(np.nanmedian(b)):.1f} "
            f"loc_med={float(np.nanmedian(v)):.1f} loc_p90={float(np.nanquantile(v, 0.9)):.1f}",
            flush=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
