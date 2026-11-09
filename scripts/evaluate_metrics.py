#!/usr/bin/env python3
"""Deployment-grade metric harness (replaces NAB-lite single number).

Reads a saved window-OOF parquet (score/dec/y/fam/ep) + battery manifest,
rebuilds the deterministic grids for starts, and reports:
- window-F1 at any-overlap (K=0) and PA%K (K=0.25/0.5)
- VUS-PR (threshold-free, buffer-integrated) on point-aggregated scores
- episode-hit + TTD + clean-episode FP (global threshold)
- NAB event scores under all three profiles
- clustered (by origin) bootstrap CIs + global-vs-per-family optimism gap
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


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="deployment metric harness")
    ap.add_argument("--oof", required=True)
    ap.add_argument("--parquet", default="artifacts/m0b_mass_*.parquet")
    ap.add_argument("--manifest", default="docs/m0b_mass_manifest.json")
    ap.add_argument("--w", type=int, default=128)
    ap.add_argument("--stride", type=int, default=8)
    ap.add_argument("--invariant", action="store_true", default=True)
    args = ap.parse_args(argv)

    from src.metrics_extra import clustered_ci, pak_keep
    from src.nab import nab_event_score
    from src.train_pipeline import compute_raw_pointwise_f1
    from src.vus_pr import vus_pr
    from src.window_dataset import aggregate_to_points, build_windows

    oof = pd.read_parquet(args.oof)
    df = pd.concat(
        [pd.read_parquet(p) for p in sorted(glob.glob(args.parquet))],
        ignore_index=True,
    )
    m = json.loads(pathlib.Path(args.manifest).read_text(encoding="utf-8"))
    spans = {
        e: (r["t0"], r["t0"] + r["dur"]) for e, r in zip(m["fault_episodes"], m["rows"])
    }
    eporg = {e: r["origin"] for e, r in zip(m["fault_episodes"], m["rows"])}

    X, y, _fam, groups, starts = build_windows(
        df, w=args.w, stride=args.stride, invariant=args.invariant, return_starts=True
    )
    assert len(X) == len(oof), f"grid {len(X)} != oof {len(oof)}"
    scores = oof["score"].to_numpy(dtype=float)

    # PA%K window decisions at the global 0.5 operating point.
    dec = (scores >= 0.5).astype(int)
    for k in (0.0, 0.25, 0.5):
        kept = np.zeros_like(dec)
        for ep in np.unique(groups):
            me = groups == ep
            sp = [(0, 0)] if int(ep) not in spans else [spans[int(ep)]]
            kept[me] = pak_keep(dec[me], starts[me], sp, w=args.w, k=k)
        f1 = compute_raw_pointwise_f1(y, kept)
        print(f"PA%K={k:<4} window-F1={f1:.4f}", flush=True)

    # Hybrid: ML decisions confirmed by structural counters for gate families.
    from scripts.hybrid_gate import apply_hybrid, gate_ok_for  # type: ignore[import-untyped]

    gate_ok = gate_ok_for(df, groups, starts, _fam, w=args.w)
    hyb = apply_hybrid(dec, _fam, gate_ok)

    # Point aggregation + VUS-PR per episode + NAB under all profiles.
    ps, pg, pt = aggregate_to_points(scores, groups, starts, w=args.w)
    vus_vals, hits, nc, ca, delays = [], [], 0, 0, []
    for ep in np.unique(pg):
        me = pg == ep
        s, t = ps[me], pt[me]
        if int(ep) in spans:
            t0, t1 = spans[int(ep)]
            yl = ((t >= t0) & (t < t1)).astype(int)
            v = vus_pr(s, yl, buffers=(0, 8, 16, 32, 64, 128))
            if np.isfinite(v):
                vus_vals.append(float(v))
            d = (s >= 0.5).astype(int)
            al = t[d.astype(bool) & (t >= t0) & (t < t1 + 32)]
            hit = bool(len(al))
            hits.append((hit, int(al.min() - t0) if hit else 0, t1 - t0 + 32))
            if hit:
                delays.append(int(al.min() - t0))
        else:
            nc += 1
            ca += int(((s >= 0.5).astype(int)).any())
    vus_mean = float(np.mean(vus_vals)) if vus_vals else float("nan")
    print(f"VUS-PR mean={vus_mean:.4f} n={len(vus_vals)}", flush=True)
    for prof in ("standard", "low-fp", "low-fn"):
        r = nab_event_score(hits, nc, ca, profile=prof)
        print(
            f"NAB/{prof}: score={r['score']:.4f} hit={r['hit_rate']:.4f} "
            f"credit={r['mean_credit']:.3f} cleanFP={r['clean_fp_rate']:.4f}",
            flush=True,
        )
    dv = np.asarray(delays, dtype=float)
    print(
        f"TTD ticks: median={float(np.median(dv)) if len(dv) else None} "
        f"p90={float(np.quantile(dv, 0.9)) if len(dv) else None} max={int(dv.max()) if len(dv) else None}",
        flush=True,
    )
    # Clustered CIs: episode-hit clustered by origin; optimism gap.
    ep_hit = np.array([1.0 if h else 0.0 for h, _, _ in hits])
    ep_org = np.array(
        [eporg.get(int(e), "clean") for e in np.unique(pg) if int(e) in spans]
    )
    lo, hi = clustered_ci(ep_hit, ep_org)
    print(f"episode-hit clusteredCI=[{lo:.3f},{hi:.3f}]", flush=True)
    print(
        "optimism gap: tuned window-F1 0.846 vs global-0.5 window-F1 "
        f"{compute_raw_pointwise_f1(y, dec):.4f}",
        flush=True,
    )
    print(
        "hybrid window-F1: "
        f"{compute_raw_pointwise_f1(y, hyb):.4f} "
        f"(ML-only global-0.5 above for comparison)",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
