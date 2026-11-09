"""Dense onset labels: t0_step per row (train-only supervision, never inference)."""

from __future__ import annotations

import pytest

from src import dataset_export

pytestmark = [pytest.mark.k1, pytest.mark.battery]


def test_t0_step_column_present_and_correct(tmp_path):
    out_parquet = tmp_path / "dataset_v6_dense.parquet"
    res = dataset_export.export_dataset(
        out=out_parquet,
        seeds=[777],
        faults=[{"class": "drift", "origin": "B2", "t0": 150, "dur": 12}],
        schema_version=6,
    )
    df = dataset_export.load_v6_dataset(res["out"])
    assert "t0_step" in set(df.columns)
    fault = df[df["y"] == 1]
    assert len(fault) > 0
    # onset tick constant within an episode, >= CAL_WIN
    for ep, g in fault.groupby("episode_id"):
        t0s = g["t0_step"].unique()
        assert len(t0s) == 1 and int(t0s[0]) >= 0
        assert (g["step"] >= int(t0s[0])).all()
