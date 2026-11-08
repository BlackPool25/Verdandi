"""Frozen-182 v6 export tests (fast: subset only)."""

from __future__ import annotations


def test_export_two_episodes_has_v6_contract(tmp_path):
    from scripts.export_m0b_v6 import export_subset

    df = export_subset(clean_seed=30201, fault_id="F-06", out=str(tmp_path / "t.parquet"))
    assert set(df["episode_id"]) == {30201, 30001}
    assert {"fault_family", "y", "step"} <= set(df.columns) and len(df) > 0
