"""Trailing buffer/flow window stats, aligned to built window rows (causal)."""

import numpy as np


def build_flow_features(df, groups, starts, w: int, jobs: int = 1):
    """Per (episode, window-start): trailing mean+max of buffer/flow cols.

    Pure trailing windows over step-sorted episode frames — identical
    under future masking by construction (test pins this).
    jobs>1 fans episodes out to worker processes (order-preserving).
    """
    import pandas as pd

    cols = [c for c in df.columns if c.startswith("buffer_")] + [
        c for c in ("sunk", "scrapped", "scrapped_total", "throughput") if c in df.columns
    ]
    out = np.zeros((len(groups), 2 * max(1, len(cols))))
    if not cols:
        return out
    eps = list(pd.unique(groups))
    if jobs is None or jobs < 2:
        parts = [_episode_flow(df, ep, groups, starts, cols, w) for ep in eps]
    else:
        from concurrent.futures import ProcessPoolExecutor

        import pickle

        payload = pickle.dumps((df, cols, w))
        with ProcessPoolExecutor(max_workers=jobs) as ex:
            parts = list(
                ex.map(
                    _episode_flow_worker,
                    [(payload, ep, groups, starts) for ep in eps],
                    chunksize=64,
                )
            )
    for idx, block in parts:
        out[idx] = block
    return out


def _episode_flow_worker(args):
    import pickle

    payload, ep, groups, starts = args
    df, cols, w = pickle.loads(payload)
    return _episode_flow(df, ep, groups, starts, cols, w)


def _episode_flow(df, ep, groups, starts, cols: list, w: int):
    g = df[df["episode_id"] == ep].sort_values("step").reset_index(drop=True)
    mat = g[cols].to_numpy(dtype=float)
    idx = np.where(np.asarray(groups) == ep)[0]
    block = np.zeros((len(idx), 2 * len(cols)))
    for k, i in enumerate(idx):
        s = int(starts[i])
        seg = mat[max(0, s - w) : s] if s > 0 else mat[0:0]
        if len(seg) == 0:
            continue
        block[k, 0::2] = seg.mean(axis=0)
        block[k, 1::2] = seg.max(axis=0)
    return idx, block
