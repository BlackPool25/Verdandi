"""Tabular OOF experts tests (tiny subset; full run is scripts/train_tabular.py main)."""

from __future__ import annotations

import numpy as np


def test_tabular_oof_runs_and_signs_hold(tmp_path):
    from scripts.train_tabular import train_oof_subset

    out = train_oof_subset(n_episodes=4, n_splits=2, out=str(tmp_path / "oof.parquet"))
    assert {"knn", "lof", "supervised_lr", "y", "episode_id"} <= set(out.columns)
    assert {"ecod", "iforest"} & set(out.columns) == set()
    assert np.isfinite(out["lof"]).all()


def test_pruned_makers_are_contributors_only():
    from scripts.train_tabular import makers

    assert set(makers()) == {"knn", "pca", "lof", "supervised_lr"}


def test_supervised_lr_balanced_ranks_minority_above_majority():
    from scripts.train_tabular import _supervised_lr

    rng = np.random.default_rng(0)
    x_maj = rng.normal(0, 1, size=(90, 2))
    x_min = rng.normal(4, 1, size=(10, 2))
    x = np.vstack([x_maj, x_min])
    y = np.array([0] * 90 + [1] * 10)
    scorer = _supervised_lr(x, y)
    s = np.asarray(scorer(x))
    assert np.isfinite(s).all() and float(s[y == 1].mean()) > float(s[y == 0].mean())


def test_dlinear_and_mp_confirm_columns_exist(tmp_path):
    from scripts.train_tabular import train_oof_subset

    out = train_oof_subset(n_episodes=4, n_splits=2, out=str(tmp_path / "oof15.parquet"))
    assert "dlinear" in out.columns and "mp_confirm" in out.columns
    assert out["mp_confirm"].dtype == bool
