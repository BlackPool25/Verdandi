"""Open-set LambdaRank attribution (TDD RED)."""

import numpy as np


def _toy():
    rng = np.random.default_rng(0)
    # 4 queries x 3 candidates; candidate 0 is the root (high dev+z_rank feats)
    X, g = [], []
    for _ in range(4):
        base = rng.normal(0, 0.2, size=(3, 2))
        base[0] += np.array([3.0, 2.0])
        X.append(base)
        g.append(3)
    return np.vstack(X), np.array(g), np.tile([1, 0, 0], 4)


def test_ranker_top1_picks_root():
    from src.ranker import train_ranker

    X, groups, y = _toy()
    model = train_ranker(X, y, groups)
    from src.ranker import top1
    hits = 0
    for q in range(4):
        if top1(model, X[q * 3:(q + 1) * 3]) == 0:
            hits += 1
    assert hits >= 3


def test_ranker_rejects_unseen_machine_shape():
    # open-set: scoring works for a candidate count never seen in train
    from src.ranker import score_candidates, train_ranker

    X, groups, y = _toy()
    model = train_ranker(X, y, groups)
    rng = np.random.default_rng(1)
    Xnew = rng.normal(0, 1, size=(5, 2))
    s = score_candidates(model, Xnew)
    assert s.shape == (5,) and np.all(np.isfinite(s))
