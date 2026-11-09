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


def test_quality_faults_long_enough_to_emit_rejects():
    from scripts.gen_supplement import build_supplement_specs

    _, _, faults, _, _ = build_supplement_specs(
        n_per_cell=4, n_clean=2, n_doubles=4, episode_len=1000, seed=11
    )
    qdurs = [
        f["dur"] for f in faults.values()
        if isinstance(f, dict) and f["class"] == "quality"
    ]
    assert qdurs and min(qdurs) >= 25


def test_dr_texture_capped_for_snr_floor():
    from scripts.gen_supplement import build_supplement_specs

    _, _, _, textures, _ = build_supplement_specs(
        n_per_cell=2, n_clean=1, n_doubles=0, episode_len=1000, seed=11
    )
    for t in textures.values():
        assert 0.3 <= t["eps_scale"] <= 0.5
        assert 0.0 <= t["sine_amp"] <= 1.0


def test_quality_faults_carry_rate_floor():
    from scripts.gen_supplement import build_supplement_specs

    _, _, faults, _, _ = build_supplement_specs(
        n_per_cell=4, n_clean=2, n_doubles=4, episode_len=1000, seed=11
    )
    rates = [
        f["extra"]["reject_rate"] for f in faults.values()
        if isinstance(f, dict) and f["class"] == "quality"
    ]
    assert rates and min(rates) >= 0.3
