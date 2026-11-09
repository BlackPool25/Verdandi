"""Family head: 7-class fault typing with per-family operating points (TDD RED)."""

import numpy as np


def _toy():
    rng = np.random.default_rng(0)
    # 3 families, separable clusters
    X = np.vstack([
        rng.normal([0, 0], 0.5, (20, 2)),
        rng.normal([5, 0], 0.5, (20, 2)),
        rng.normal([0, 5], 0.5, (20, 2)),
    ])
    y = np.array(["bias"] * 20 + ["drift"] * 20 + ["spike"] * 20)
    return X, y


def test_family_head_top1_and_threshold():
    from src.family_head import tune_thresholds, train_family_head

    X, y = _toy()
    model, classes = train_family_head(X, y)
    pred, conf = model_predict(model, classes, X[:3])
    assert set(pred) <= set(classes)
    assert np.all((conf >= 0) & (conf <= 1))
    thr = tune_thresholds(
        np.array(["bias"] * 20 + ["drift"] * 20 + ["spike"] * 20),
        np.tile(np.eye(3), (20, 1)),
        classes,
    )
    assert set(thr) == set(classes) and all(0 < t < 1 for t in thr.values())


def model_predict(model, classes, X):
    from src.family_head import predict_family

    return predict_family(model, classes, X)
