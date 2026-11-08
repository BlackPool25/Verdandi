"""OOF harness tests: every row scored once, from a model blind to its episode."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.oof import run_oof


def _four_episode_df() -> pd.DataFrame:
    rng = np.random.default_rng(0)
    frames = []
    for ep in range(4):
        n = 20
        a = rng.normal(0, 1, size=n)
        b = rng.normal(0, 1, size=n)
        y = np.zeros(n, dtype=int)
        if ep % 2 == 0:
            a[10] += 8.0
            y[10] = 1
        frames.append(pd.DataFrame({"episode_id": ep, "y": y, "a": a, "b": b}))
    return pd.concat(frames, ignore_index=True)


def _mean_dist(X_train: np.ndarray, y_train: np.ndarray):
    mu = X_train[np.asarray(y_train) == 0].mean(axis=0)
    return lambda x: np.abs(np.asarray(x, dtype=float) - mu).sum(axis=1)


def test_oof_scores_every_row_once_from_unseen_episode():
    df = _four_episode_df()
    out = run_oof(df, ["a", "b"], {"mean_dist": _mean_dist}, n_splits=2)
    assert len(out) == len(df) and out["mean_dist"].notna().all()
    assert (out["mean_dist"] > 0).any()
    assert out["mean_dist"].loc[out["y"] == 1].mean() > out["mean_dist"].loc[
        out["y"] == 0
    ].mean()
