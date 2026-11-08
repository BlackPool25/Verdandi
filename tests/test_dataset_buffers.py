"""Buffer channel correctness (verified misalignment fix).

rec["buffers"] is BUFFERS-ordered gap buffers; the export must expose them
under gap names, and buffer_occ must equal plant-total WIP (causal, no //5).
"""

from __future__ import annotations

import pytest

from src import config, dataset_export, twin

pytestmark = [pytest.mark.k1, pytest.mark.k3, pytest.mark.battery]


def test_gap_columns_use_buffer_names_not_machine_names(tmp_path):
    res = dataset_export.export(seed=7, out=tmp_path / "d.parquet")
    df = dataset_export.load_dataset(res["out"])
    for gap in config.BUFFERS:
        assert f"buffer_{gap}" in df.columns, gap
    for m in config.MACHINE_NAMES:
        assert f"buffer_{m}" not in df.columns, m


def test_gap_values_match_buf_rows_order(tmp_path):
    rec = twin.run_episode(7, None)
    res = dataset_export.export(seed=7, out=tmp_path / "d.parquet")
    df = dataset_export.load_dataset(res["out"])
    order = list(config.BUFFERS)
    for step in (15, 120, 200):
        for j, gap in enumerate(order):
            assert (
                df.loc[df["step"] == step, f"buffer_{gap}"].iloc[0]
                == rec["buffers"][j][step]
            )


def test_buffer_occ_is_plant_total_wip(tmp_path):
    rec = twin.run_episode(7, None)
    res = dataset_export.export(seed=7, out=tmp_path / "d.parquet")
    df = dataset_export.load_dataset(res["out"])
    for step in (15, 120, 200, 299):
        total = sum(rec["buffers"][j][step] for j in range(config.N_BUFFERS))
        assert df.loc[df["step"] == step, "buffer_occ"].iloc[0] == total
