"""Todo 9 battery contract (topology-A, schema v2): TDD red-first.

Encodes the full-battery re-baseline contract BEFORE the battery runs:
manifest 182, per-seed determinism, wall budget, 7-class injectability on
the 26-roster, duty tolerances, battery_id + schema_version tagging, and
the F-21 t0-shift bite probe. The evidence-JSON test is RED until the
battery lands docs-battery-topology-A-full182.json.
"""

import copy
import json
import pathlib

import pytest

from src import twin
from src.config import CODE_VERSION, TWIN_SCHEMA

pytestmark = pytest.mark.battery

BATTERY_ID_FULL = "topology-A-full182"
BATTERY_ID_QUICK = "topology-A-quick16"
SEEDS = [777, 1234, 999, 42, 2026]
EVIDENCE_JSON = (
    pathlib.Path(__file__).resolve().parent.parent
    / "docs-battery-topology-A-full182.json"
)

_F21_B2 = {
    "id": "F-21",
    "class": "drift",
    "origin": "B2",
    "t0": 150,
    "dur": 12,
    "mag_sigma": 5.2,
}


def test_battery_ids_and_schema_pinned():
    assert BATTERY_ID_FULL == "topology-A-full182"
    assert BATTERY_ID_QUICK == "topology-A-quick16"
    assert TWIN_SCHEMA == 2
    assert CODE_VERSION == "twin-2.1.0-topology-A"


def test_manifest_182_full_coverage():
    manifest = twin.build_faults()
    assert len(manifest) == 182 == 26 * 7
    assert twin.validate_manifest(manifest) == []
    have_mc = {(r["origin"], r["class"]) for r in manifest}
    assert len(twin.MACHINES) == 26
    for m in twin.MACHINES:
        for c in twin._FAULT_CLASSES:
            assert (m, c) in have_mc
    assert len(twin._FAULT_CLASSES) == 7
    assert sum(1 for r in manifest if r.get("rep")) == 7


def test_per_seed_determinism_f21():
    for seed in SEEDS:
        a = twin.replay_digest(twin.run_episode(seed, copy.deepcopy(_F21_B2)))
        b = twin.replay_digest(twin.run_episode(seed, copy.deepcopy(_F21_B2)))
        assert a == b


def test_t0_shift_bites_digest():
    base = twin.replay_digest(twin.run_episode(777, copy.deepcopy(_F21_B2)))
    shifted = copy.deepcopy(_F21_B2)
    shifted["t0"] = 151
    other = twin.replay_digest(twin.run_episode(777, shifted))
    assert other != base


def test_duty_within_t6r_tolerances():
    for seed in SEEDS:
        rec = twin.run_episode(seed, None, enable_natural_breakdown=True)
        d = twin.duty_cycle(rec)
        assert d["run_share"] >= 0.80, (seed, d)
        assert d["starved_share"] <= 0.15, (seed, d)
        assert d["xfer_open"] == 0, (seed, d)
        assert d["pileup_violations"] == [], (seed, d)


def test_wall_budget_fixture_math():
    total, tripped = twin.check_wall_tripwire([100.0, 110.0, 90.0, 80.0])
    assert (total, tripped) == (380.0, False)
    assert twin._BATTERY_BUDGET_S == 600.0


def test_full182_evidence_json_landed():
    """RED until Todo 9 runs the full battery and writes the evidence JSON."""
    payload = json.loads(EVIDENCE_JSON.read_text())
    assert payload["battery_id"] == BATTERY_ID_FULL
    assert payload["schema_version"] == 2
    assert payload["code_version"] == "twin-2.1.0-topology-A"
    assert payload["manifest_rows"] == 182
    assert payload["wall_report"]["wall_total_s"] < 600.0
    assert payload["verdict"] == "PASS"
    assert payload["diverge"] == 0
    assert payload["t"] == 300
    for key in ("joined_digest", "quick16_digest", "wall_report", "duty"):
        assert key in payload
