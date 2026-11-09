"""Long-episode export tests: episode_len + texture thread through export."""

import pytest

pytestmark = [pytest.mark.k1, pytest.mark.battery]


def test_export_long_episode_row_count(tmp_path):
    from src import dataset_export

    out = tmp_path / "long_v6.parquet"
    res = dataset_export.export_dataset(
        out=out,
        seeds=[777],
        faults=[{"class": "drift", "origin": "B2", "t0": 150, "dur": 12}],
        schema_version=6,
        episode_len=400,
    )
    df = dataset_export.load_v6_dataset(res["out"])
    assert int(df["step"].max()) == 399
    assert (df["t0_step"] == 150).any()
