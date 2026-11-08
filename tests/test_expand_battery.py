"""Supplement-battery smoke (2 episodes; frozen-182 never modified)."""

from __future__ import annotations

import pathlib


def test_supplement_manifest_schema_and_no_overlap(tmp_path):
    from scripts.expand_m0b_battery import build_supplement

    out = tmp_path / "supplement.json"
    m = build_supplement(str(out), n_per_family=1, seed=7)
    assert {"fault_episodes", "clean_episodes", "rows"} <= set(m)
    assert len(m["fault_episodes"]) == 3 and len(m["rows"]) == 3
    import json

    frozen = json.loads(pathlib.Path("docs/m0b_battery_manifest.json").read_text())
    assert not (set(m["fault_episodes"]) & set(frozen["fault_episodes"]))
    assert not (set(m["clean_episodes"]) & set(frozen["clean_episodes"]))
    # Deterministic: same seed rebuilds identical manifest.
    m2 = build_supplement(str(tmp_path / "s2.json"), n_per_family=1, seed=7)
    assert m["fault_episodes"] == m2["fault_episodes"]


def test_supplement_export_runs_and_matches_v6_contract(tmp_path):

    from scripts.expand_m0b_battery import build_supplement
    from scripts.export_m0b_v6 import export_subset  # noqa: F401 (contract ref)
    from src import dataset_export

    m = build_supplement(str(tmp_path / "sup.json"), n_per_family=1, seed=11)
    ep = m["fault_episodes"][0]
    row = dict(m["rows"][0])
    res = dataset_export.export_v6(
        seeds=[m["clean_episodes"][0], ep],
        out=str(tmp_path / "t.parquet"),
        faults={ep: row},
        enable_natural_breakdown=False,
    )
    df = dataset_export.load_v6_dataset(res["out"])
    assert set(df["episode_id"]) == {m["clean_episodes"][0], ep}
    assert {"fault_family", "y", "step"} <= set(df.columns) and len(df) > 0
