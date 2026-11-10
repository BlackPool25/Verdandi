"""Trailing buffer/flow window stats, aligned to built window rows (causal)."""

import numpy as np


def build_flow_features(df, groups, starts, w: int):
    """Per (episode, window-start): trailing mean+max of buffer/flow cols.

    Pure trailing windows over step-sorted episode frames — identical
    under future masking by construction (test pins this).
    """
    import pandas as pd

    cols = [c for c in df.columns if c.startswith("buffer_")] + [
        c for c in ("sunk", "scrapped", "scrapped_total", "throughput") if c in df.columns
    ]
    out = np.zeros((len(groups), 2 * max(1, len(cols))))
    if not cols:
        return out
    for ep in pd.unique(groups):
        g = df[df["episode_id"] == ep].sort_values("step").reset_index(drop=True)
        mat = g[cols].to_numpy(dtype=float)
        idx = np.where(np.asarray(groups) == ep)[0]
        for k, i in enumerate(idx):
            s = int(starts[i])
            seg = mat[max(0, s - w) : s] if s > 0 else mat[0:0]
            if len(seg) == 0:
                continue
            out[i, 0::2] = seg.mean(axis=0)
            out[i, 1::2] = seg.max(axis=0)
    return out
