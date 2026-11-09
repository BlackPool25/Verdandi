#!/usr/bin/env python3
"""Multi-scale fusion eval (reshape step): fuse w32 + w128 OOF scores at point
level (darts pattern), threshold once, score NAB-style events.

Reads two --save-oof parquets (must share the same battery + grid origin;
row order is rebuilt deterministically, never assumed to align).
"""

from __future__ import annotations

import argparse
import glob
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd  # type: ignore[import-untyped]


def fuse_point_scores(
    oof_a: pd.DataFrame,
    oof_b: pd.DataFrame,
    df: pd.DataFrame,
    *,
    w_a: int,
    w_b: int,
    stride: int,
    offset: int = 0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Mean-fuse two width scales at point level.

    Rebuilds both grids with starts (deterministic), aggregates each scale's
    OOF scores to points, averages. Returns (fused, episode, step).
    """
    from src.window_dataset import aggregate_to_points, build_windows

    out = None
    for oof, w in ((oof_a, w_a), (oof_b, w_b)):
        X, _y, _fam, groups, starts = build_windows(
            df,
            w=w,
            stride=stride,
            offset=offset,
            invariant=True,
            return_starts=True,
        )
        assert len(X) == len(oof), f"{w}: grid {len(X)} != oof {len(oof)}"
        ps, pg, pt = aggregate_to_points(oof["score"].to_numpy(), groups, starts, w=w)
        key = list(zip(pg.tolist(), pt.tolist()))
        if out is None:
            out = {k: [v] for k, v in zip(key, ps.tolist())}
            order, ep, st = key, pg, pt
        else:
            assert [k for k in key] == order, "scale grids do not align"
            for k, v in zip(key, ps.tolist()):
                out[k].append(v)
    fused = np.array([np.mean(out[k]) for k in order])
    return fused, np.asarray(ep), np.asarray(st)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="fuse two OOF scales at point level")
    ap.add_argument("--oof-a", required=True)
    ap.add_argument("--oof-b", required=True)
    ap.add_argument("--w-a", type=int, default=32)
    ap.add_argument("--w-b", type=int, default=128)
    ap.add_argument("--stride", type=int, default=8)
    ap.add_argument("--parquet", default="artifacts/m0b_mass_*.parquet")
    args = ap.parse_args(argv)
    import json

    from src.nab import nab_event_score

    oof_a = pd.read_parquet(args.oof_a)
    oof_b = pd.read_parquet(args.oof_b)
    paths = sorted(glob.glob(args.parquet))
    df = pd.concat([pd.read_parquet(p) for p in paths], ignore_index=True)
    fused, ep, st = fuse_point_scores(
        oof_a, oof_b, df, w_a=args.w_a, w_b=args.w_b, stride=args.stride
    )
    manifest = json.loads(
        pathlib.Path("docs/m0b_mass_manifest.json").read_text(encoding="utf-8")
    )
    y = np.zeros(len(ep))

    # Point labels from the battery rows (fault spans), not window labels.
    spans = {
        e: (r["t0"], r["t0"] + r["dur"])
        for e, r in zip(manifest["fault_episodes"], manifest["rows"])
    }
    for i, (e, t) in enumerate(zip(ep.tolist(), st.tolist())):
        if e in spans and spans[e][0] <= t < spans[e][1]:
            y[i] = 1
    from src.train_pipeline import compute_raw_pointwise_f1

    for thr in (0.3, 0.4, 0.5, 0.6):
        dec = (fused >= thr).astype(int)
        f1 = compute_raw_pointwise_f1(y, dec)
        hits, n_clean, clean_al = [], 0, 0
        for e in np.unique(ep):
            m_ = ep == e
            d, t = dec[m_], st[m_]
            if int(e) in spans:
                t0, t1 = spans[int(e)]
                in_span = (t >= t0) & (t < t1 + 32)
                al = t[d.astype(bool) & in_span]
                hit = bool(len(al))
                delay = int(al.min() - t0) if hit else 0
                hits.append((hit, max(0, delay), t1 - t0 + 32))
            else:
                n_clean += 1
                clean_al += int(d.any())
        r = nab_event_score(hits, n_clean, clean_al, profile="low-fn")
        print(
            f"thr={thr:.1f} point-F1={f1:.4f} hit={r['hit_rate']:.4f} "
            f"credit={r['mean_credit']:.3f} cleanFP={r['clean_fp_rate']:.4f} "
            f"NAB(low-fn)={r['score']:.4f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
