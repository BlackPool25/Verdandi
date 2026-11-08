"""M0b battery freeze tests (Phase B1): manifest determinism, schema, budget, pins.

The frozen 182-row machine×class matrix + episode assignment is the battery
freeze artifact. Tests pin it; scripts/freeze_m0b_battery.py produces it.
"""

from __future__ import annotations

import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))

import freeze_m0b_battery as fz

pytestmark = [pytest.mark.k3, pytest.mark.battery]

GATEWAY = frozenset({"ASM0", "ASM1", "INSP0", "ASM2", "RWK0"})
N_MACHINES = 26
N_CLASSES = 7


def test_manifest_deterministic_across_runs(tmp_path):
    a = fz.build_manifest(master_seed=777)
    b = fz.build_manifest(master_seed=777)
    assert a["rows"] == b["rows"]
    assert a["sha256"] == b["sha256"]
    out_a = tmp_path / "a.json"
    out_b = tmp_path / "b.json"
    assert fz.main(["--out", str(out_a)]) == 0
    assert fz.main(["--out", str(out_b)]) == 0
    assert out_a.read_bytes() == out_b.read_bytes()


def test_manifest_schema_full_matrix():
    m = fz.build_manifest(master_seed=777)
    rows = m["rows"]
    assert len(rows) == N_MACHINES * N_CLASSES
    pairs = {(r["origin"], r["class"]) for r in rows}
    assert len(pairs) == N_MACHINES * N_CLASSES
    for r in rows:
        assert {
            "id",
            "class",
            "origin",
            "t0",
            "dur",
            "mag_sigma",
            "extra",
            "mag_rung",
        } <= set(r)


def test_rate_budget_capped():
    m = fz.build_manifest(master_seed=777)
    exempt = set()
    for r in m["rows"]:
        if not r["rep"]:
            assert r["dur"] <= 14, r["id"]
        if r["class"] == "breakdown":
            mult = float(r["extra"].get("mttr_mult", 1.0))
            import math

            if r["rep"]:
                # Oracle rep pins are exempt by twin contract (F-25 known-breach).
                if r["dur"] * math.ceil(mult) > 14:
                    exempt.add(r["id"])
                continue
            assert r["dur"] * math.ceil(mult) <= 14, r["id"]
    assert exempt == {"F-25"}, exempt


def test_oracle_rep_pins_present():
    m = fz.build_manifest(master_seed=777)
    by_id = {r["id"]: r for r in m["rows"]}
    for pin in ("F-06", "F-21", "F-22", "F-23"):
        assert pin in by_id, pin
        assert by_id[pin]["rep"] is True


def test_gateway_share_logged_with_waiver():
    m = fz.build_manifest(master_seed=777)
    gw = [r for r in m["rows"] if r["origin"] in GATEWAY]
    assert len(gw) == 35
    assert m["gateway_share"] == len(gw) / len(m["rows"])
    assert m["gateway_quota_waived_to"] == ">=19%"


def test_episode_assignment_deterministic_no_overlap():
    m = fz.build_manifest(master_seed=777)
    fault_eps = m["fault_episodes"]
    clean_eps = m["clean_episodes"]
    assert len(fault_eps) == N_MACHINES * N_CLASSES
    assert len(clean_eps) == 10
    assert len(set(fault_eps) & set(clean_eps)) == 0
    assert m["episode_seeds"] == sorted(m["episode_seeds"])
