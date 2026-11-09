"""Supplement battery tests: long-episode + DR + doubles, new battery ID."""

import json

import pytest

pytestmark = [pytest.mark.battery]


def test_supplement_tiny_run(tmp_path):
    from scripts.gen_supplement import main

    man = tmp_path / "supp_manifest.json"
    out = tmp_path / "supp.parquet"
    rc = main(
        [
            "--n-per-cell",
            "1",
            "--n-clean",
            "2",
            "--n-doubles",
            "2",
            "--episode-len",
            "1000",
            "--seed",
            "7",
            "--manifest",
            str(man),
            "--out",
            str(out),
            "--shard-eps",
            "50",
        ]
    )
    assert rc == 0
    manifest = json.loads(man.read_text())
    assert manifest["battery_id"] == "m0b-mass-supplement-v1"
    assert manifest["episode_len"] == 1000
    assert manifest["n_doubles"] >= 2
    gaps = [d["gap"] for d in manifest["doubles"]]
    assert all(isinstance(g, int) and g >= 0 for g in gaps)
