"""Open-set LambdaRank attribution head (Head-A ranker).

Per-(episode,machine) scoring: any candidate count at serve time.
GroupKFold by episode-family at train; groups = per-query row counts.
"""

from __future__ import annotations

import numpy as np


def train_ranker(
    X: np.ndarray,
    y: np.ndarray,
    groups: np.ndarray,
    seed: int = 0,
) -> object:
    import lightgbm as lgb  # type: ignore[import-untyped]

    order = np.argsort(np.asarray(groups), kind="stable")
    Xs = np.asarray(X)[order]
    ys = np.asarray(y)[order]
    qids = np.asarray(groups)[order]
    _, group = np.unique(qids, return_counts=True)
    group = [int(v) for v in group]
    ranker = lgb.LGBMRanker(
        objective="lambdarank",
        lambdarank_truncation_level=5,
        lambdarank_norm=True,
        num_leaves=7,
        min_data_in_leaf=5,
        n_estimators=50,
        random_state=seed,
        verbose=-1,
    )
    ranker.fit(Xs, ys, group=group)
    return ranker


def score_candidates(model: object, Xq: np.ndarray) -> np.ndarray:
    return np.asarray(model.predict(np.asarray(Xq)), dtype=float)


def top1(model: object, Xq: np.ndarray) -> int:
    return int(np.argmax(score_candidates(model, Xq)))
