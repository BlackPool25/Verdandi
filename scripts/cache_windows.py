"""Build once, stream per shard: window cache reused by every eval.

Never concats raw shards (1.37M rows OOMs). Per-shard peak ~300MB.
Flow features via vectorized groupby-transform (no per-episode pickle).
Run: python3 scripts/cache_windows.py  (writes artifacts/window_cache/)
"""

import numpy as np
import pandas as pd

CACHE_DIR = "artifacts/window_cache"


def _flow_block(df, groups, starts, w: int):
    """Vectorized trailing mean+max per buffer/flow col (groupby-transform).

    rolling(w).mean/max shifted by 1 == window [s-w, s) in positional
    row space. Gathered at window starts.
    """
    cols = [c for c in df.columns if c.startswith("buffer_")] + [
        c for c in ("sunk", "scrapped", "scrapped_total", "throughput") if c in df.columns
    ]
    n = len(groups)
    out = np.zeros((n, 2 * max(1, len(cols))))
    if not cols:
        return out
    g = df.sort_values(["episode_id", "step"]).reset_index(drop=True)
    ep = g["episode_id"].to_numpy()
    _, first = np.unique(ep, return_index=True)
    base = dict(zip(ep[first], first))
    rolled_mean = {}
    rolled_max = {}
    for c in cols:
        s = pd.Series(g[c].to_numpy(dtype=float))
        rolled_mean[c] = s.groupby(ep).transform(
            lambda x: x.rolling(w, min_periods=1).mean().shift(1).fillna(0.0)
        ).to_numpy()
        rolled_max[c] = s.groupby(ep).transform(
            lambda x: x.rolling(w, min_periods=1).max().shift(1).fillna(0.0)
        ).to_numpy()
    for i in range(n):
        r = base[groups[i]] + int(starts[i])
        for j, c in enumerate(cols):
            out[i, 2 * j] = rolled_mean[c][r]
            out[i, 2 * j + 1] = rolled_max[c][r]
    return out


def main(glob: str | None = None, out: str | None = None):
    import pathlib

    from src.window_dataset import build_windows

    import glob as _glob

    outdir = pathlib.Path(out or CACHE_DIR)
    outdir.mkdir(parents=True, exist_ok=True)
    paths = sorted(_glob.glob(glob or "artifacts/m0b_mass_*.parquet"))
    acc = {"invariant": [], "identity": []}
    metas, flows = [], []
    for p in paths:
        df = pd.read_parquet(p)
        for tag, inv in (("invariant", True), ("identity", False)):
            res = build_windows(
                df, w=128, stride=8, invariant=inv, build_jobs=2,
                return_starts=True, return_roots=True,
            )
            X, y, fam, groups, starts, roots = res
            acc[tag].append(X)
            if tag == "identity":
                metas.append(pd.DataFrame({
                    "y": y, "fam": fam, "ep": groups, "start": starts,
                    "root": np.asarray(roots, dtype=str),
                }))
                flows.append(_flow_block(
                    df, np.asarray(groups), np.asarray(starts), w=128,
                ))
        del df
        print(f"cached shard {p.split('_')[-1]}", flush=True)
    for tag, parts in acc.items():
        np.save(outdir / f"X_{tag}.npy", np.vstack(parts))
    meta = pd.concat(metas, ignore_index=True)
    meta.to_parquet(outdir / "meta.parquet", index=False)
    np.save(outdir / "F_flow.npy", np.vstack(flows))
    print(f"done: invariant+identity, n={len(meta)}", flush=True)


if __name__ == "__main__":
    import argparse as _ap
    _p = _ap.ArgumentParser()
    _p.add_argument("--glob", default=None)
    _p.add_argument("--out", default=None)
    _a = _p.parse_args()
    main(glob=_a.glob, out=_a.out)
