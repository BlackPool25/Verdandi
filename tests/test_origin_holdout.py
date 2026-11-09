"""Machine-holdout smoke test: split logic must produce non-empty train/test."""

import numpy as np


def test_machine_holdout_split_nonempty():
    from scripts.train_origin import _oof_predict

    rng = np.random.default_rng(0)
    X = rng.normal(0, 1, size=(60, 4))
    yr = np.array(["A0"] * 20 + ["B2"] * 20 + ["none"] * 20)
    groups = np.array([1] * 20 + [2] * 20 + [3] * 20)
    ep_root = {1: "A0", 2: "B2", 3: "none"}
    pred = _oof_predict(
        X, yr, groups, machine_holdout=["B2"], ep_root=ep_root
    )
    assert len(pred) == 60
    assert set(pred.tolist()) <= {"A0", "B2", "none"}
