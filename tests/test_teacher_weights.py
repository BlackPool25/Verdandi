"""Teacher sample-weight wiring (Task 0 spike, TDD RED)."""


def test_oof_predict_accepts_sample_weight():
    import numpy as np
    from scripts.train_origin import _oof_predict

    rng = np.random.default_rng(0)
    X = rng.normal(0, 1, (80, 6))
    yr = np.array(["a"] * 20 + ["b"] * 20 + ["c"] * 20 + ["none"] * 20)
    groups = np.repeat(np.arange(8), 10)
    w = np.ones(80)
    pred, proba, classes = _oof_predict(X, yr, groups, n_splits=2, sample_weight=w)
    assert len(pred) == 80 and proba.shape == (80, 4)
