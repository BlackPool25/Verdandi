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

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd
from joblib import load


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="trigger-gated diagnosis battery")
    ap.add_argument("--artifact", default="artifacts/window-gbm-w128-v2")
    ap.add_argument("--glob", default="artifacts/m0b_mass_*.parquet")
    ap.add_argument("--max-eps", type=int, default=110)
    ap.add_argument("--thr", type=float, default=0.8)
    ap.add_argument(
        "--rung", default="", help="filter to mag_rung (incipient/caricature)"
    )
    args = ap.parse_args(argv)

    from src.diagnose import diagnose_from_trigger
    from src.window_dataset import apply_norm, build_windows

    art = load(f"{args.artifact}/model.joblib")
    model, w, stride = art["model"], int(art["w"]), int(art["stride"])
    med = np.asarray(art["norm_median"], dtype=float)
    iqr = np.asarray(art["norm_iqr"], dtype=float)
    n_obs = int(art["n_obs_features"])
    try:
        import json

        with open(f"{args.artifact}/thresholds.json") as fh:
            fam_thr = json.load(fh)
        thr_prop = min(float(v) for k, v in fam_thr.items() if k != "none")
    except OSError:
        thr_prop = 0.5

    rows = []
    n_trig = 0
    for p in sorted(glob.glob(args.glob)):
        df = pd.read_parquet(p)
        if df["y"].sum() == 0:
            continue
        obs = [c for c in df.columns if c.startswith("obs_")]
        for fe in list(df[df.y == 1]["episode_id"].unique()):
            if len(rows) >= args.max_eps:
                break
            g = df[df.episode_id == fe].sort_values("step").reset_index(drop=True)
            r = g[g.y == 1].iloc[0]
            if args.rung and str(r["mag_rung"]) != args.rung:
                continue
            true_t0 = int(g[g.y == 1]["step"].min())
            X, _, _, _grp, starts = build_windows(
                g, w=w, stride=stride, invariant=True, return_starts=True
            )
            s = np.asarray(model.predict_proba(apply_norm(X, med, iqr, n_obs))[:, 1])
            # O2 confirm (2-of-3) at recall-first propose level; O3 global
            # confirms at dispose time (diagnose only what 0.8 would keep).
            # O4 abstain-if-unsure: anchor maxscore < hi → low-confidence.
            from src.diagnose import confirm_trigger

            trig = confirm_trigger(s, starts, thr_prop, m=2, n=3)
            if trig is None:
                rows.append(
                    (
                        r["fault_family"],
                        r["mag_rung"],
                        r["root_id_step"],
                        None,
                        None,
                        None,
                        False,
                        "unconfirmed",
                    )
                )
                continue
            m_idx = (starts >= trig - 150) & (starts <= trig + 150)
            if not m_idx.any():
                rows.append(
                    (
                        r["fault_family"],
                        r["mag_rung"],
                        r["root_id_step"],
                        None,
                        None,
                        None,
                        True,
                        "no-window",
                    )
                )
                continue
            anchor = int(starts[m_idx][int(np.argmax(s[m_idx]))])
            # O4 abstain-if-unsure (low-confidence leg only; window-margin
            # is vacuous on overlapping windows — family head needed).
            reason = "low-confidence" if float(s[m_idx].max()) < 0.9 else None
            if reason is not None:
                rows.append(
                    (
                        r["fault_family"],
                        r["mag_rung"],
                        r["root_id_step"],
                        None,
                        None,
                        None,
                        True,
                        reason,
                    )
                )
                continue
            n_trig += 1
            try:
                out = diagnose_from_trigger(g, obs, anchor)
            except Exception:  # noqa: BLE001 - harness records failures as rows
                rows.append(
                    (
                        r["fault_family"],
                        r["mag_rung"],
                        r["root_id_step"],
                        None,
                        None,
                        None,
                        True,
                        "error",
                    )
                )
                continue
            if not out:
                rows.append(
                    (
                        r["fault_family"],
                        r["mag_rung"],
                        r["root_id_step"],
                        None,
                        None,
                        None,
                        True,
                        "empty",
                    )
                )
                continue
            f0 = out[0]
            # D2 from the root candidate's own signals (not per-machine obs
            # counts): DOWN/counter at the root → process; residual-only or
            # STARVED-only → sensor (STARVED without local DOWN/counter is
            # the downstream-symptom pattern).
            struct_process = f0["onset_kind"] == "counter" or (
                f0["onset_kind"] == "state" and f0["own_state"] in ("DOWN", "BLOCKED")
            )
            pred_sp = "process" if struct_process else "sensor"
            rows.append(
                (
                    r["fault_family"],
                    r["mag_rung"],
                    r["root_id_step"],
                    f0["machine"],
                    f0["onset"] - true_t0,
                    pred_sp == r["sensor_vs_process"],
                    True,
                    "diagnosed",
                )
            )
        if len(rows) >= args.max_eps:
            break

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
