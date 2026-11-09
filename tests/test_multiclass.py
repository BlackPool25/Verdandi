"""Multiclass specialist head tests (synthetic blobs route correctly)."""

from __future__ import annotations

import numpy as np


def test_multiclass_routes_separable_families():
    from scripts.train_multiclass import train_multiclass_oof

    rng = np.random.default_rng(0)
    parts, fams, groups = [], [], []
    for i, fam in enumerate(["a", "b", "none"]):
        for ep in range(4):
            n = 20
            parts.append(rng.normal(i * 5, 1, size=(n, 4)))
            fams += [fam] * n
            groups += [i * 10 + ep] * n
    X = np.vstack(parts)
    pred = train_multiclass_oof(X, np.array(fams), np.array(groups), n_splits=2, seed=0)
    from sklearn.metrics import accuracy_score

    assert accuracy_score(fams, pred.tolist()) > 0.90
