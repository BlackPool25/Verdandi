"""Tabular OOF experts tests (tiny subset; full run is scripts/train_tabular.py main)."""

from __future__ import annotations

import numpy as np


def test_tabular_oof_runs_and_signs_hold(tmp_path):
    from scripts.train_tabular import train_oof_subset

    out = train_oof_subset(n_episodes=4, n_splits=2, out=str(tmp_path / "oof.parquet"))
    assert {"ecod", "iforest", "supervised_lr", "y", "episode_id"} <= set(out.columns)
    assert np.isfinite(out["ecod"]).all()


def test_dlinear_and_mp_confirm_columns_exist(tmp_path):
    from scripts.train_tabular import train_oof_subset

    out = train_oof_subset(n_episodes=4, n_splits=2, out=str(tmp_path / "oof15.parquet"))
    assert "dlinear" in out.columns and "mp_confirm" in out.columns
    assert out["mp_confirm"].dtype == bool
