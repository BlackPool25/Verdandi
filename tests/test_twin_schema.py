"""TDD red step (T1): schema / RNG / CAL_WIN placement tests.

Name contract (T5/T6 `-k` filters depend on it — never rename without
updating their acceptances): future flow tests MUST be named
test_agv_* (AGV pool), test_sbuf_* (SBUF overflow), test_kit_* (ASM0
kitting), test_state_* (BLOCKED/STARVED/DOWN), test_rework_* (RWK0
loop), test_fault_* (fault injection). This file owns the schema/RNG/
placement namespace only.

RED STEP: no twin logic exists yet — every test here MUST fail with
NotImplementedError until T5/T6/T7 land.
"""

import itertools
import pathlib

import pytest

from src import twin

pytestmark = pytest.mark.k1

_TWIN_SRC = pathlib.Path(__file__).resolve().parent.parent / "src" / "twin.py"

_PROBE_FAULT = {
    "id": "F-21",
    "class": "drift",
    "origin": "B5",
    "t0": 150,
    "dur": 12,
    "mag_sigma": 5.2,
}


def test_record_keys():
    rec = twin.run_episode(777, _PROBE_FAULT)
    # Full documented contract: T6 added the additive Scope channels 6/7
    # keys (throughput/events reads per TC-006b) on top of the T1 nine.
    # T-B8 adds the Table 3.1 roster snapshot (SIM_SPEC §4.4, Copilot :1161).
    assert set(rec) == {
        "seed",
        "T",
        "cal_win",
        "machines",
        "obs",
        "states",
        "buffers",
        "throughput",
        "events",
        "sbuf_stats",
        "flow_stats",
        "agv_waits",
        "parts",
        "faults",
    }


def test_record_machines_table31_per_machine():
    rec = twin.run_episode(777, _PROBE_FAULT)
    machines = rec["machines"]
    assert len(machines) == 32
    for name, cfg in machines.items():
        assert set(cfg) == {
            "class",
            "base",
            "sigma",
            "cycle",
            "mttf",
            "mttr",
            "buffer_cap",
            "transit",
        }, name
        assert cfg == dict(twin.MACHINES[name]), name


def test_record_scalars():
    rec = twin.run_episode(777, _PROBE_FAULT)
    assert rec["T"] == 300
    assert rec["cal_win"] == 120


def test_obs_shape_32x300():
    rec = twin.run_episode(777, _PROBE_FAULT)
    assert len(rec["obs"]) == 32
    assert all(len(row) == 300 for row in rec["obs"])


def test_buffer_shape_31x300():
    rec = twin.run_episode(777, _PROBE_FAULT)
    assert len(rec["buffers"]) == 31
    assert all(len(row) == 300 for row in rec["buffers"])


def test_rng_spawn_36_streams():
    twin.build_faults(777)  # raises first (red); source assert below is T7's target
    src = _TWIN_SRC.read_text()
    assert "spawn(36)" in src


def test_rng_no_bare_default_rng_int():
    twin.build_faults(777)  # raises first (red)
    src = _TWIN_SRC.read_text()
    assert "default_rng(777)" not in src
    assert "SeedSequence" in src


def test_rng_no_hash_seeding():
    twin.build_faults(777)  # raises first (red)
    src = _TWIN_SRC.read_text()
    assert "hash(" not in src


def test_cal_win_t0_in_range():
    faults = twin.build_faults(777)  # raises first (red)
    for f in faults:
        assert 120 <= f["t0"] <= 300 - f["dur"]


def test_cal_win_same_machine_gap():
    faults = twin.build_faults(777)  # raises first (red)
    by_machine: dict = {}
    for f in faults:
        by_machine.setdefault(f["origin"], []).append((f["t0"], f["dur"]))
    for windows in by_machine.values():
        windows.sort()
        for (t0a, da), (t0b, _db) in itertools.pairwise(windows):
            assert t0b - (t0a + da) >= 5


def test_cal_win_zero_faults_before_120():
    faults = twin.build_faults(777)  # raises first (red)
    assert all(f["t0"] >= 120 for f in faults)
    # _validate enforces the same floor: calibration window is fault-free.
    early = dict(_PROBE_FAULT, t0=119)
    with pytest.raises(ValueError):
        twin._validate(777, early)


def test_cal_win_t0_spread_uniform():
    faults = twin.build_faults(777)  # raises first (red)
    t0s = [f["t0"] for f in faults if not f.get("rep")]
    assert len(t0s) >= 200
    at_floor = sum(1 for t in t0s if t == 120)
    assert at_floor < 0.10 * len(t0s), f"cursor-packed: {at_floor}/{len(t0s)} at CAL_WIN"
    edges = [120, 163, 206, 249, 293]
    bins = [0, 0, 0, 0]
    for t in t0s:
        for i in range(4):
            if edges[i] <= t < edges[i + 1]:
                bins[i] += 1
                break
    for i, b in enumerate(bins):
        assert b >= 0.15 * len(t0s), f"quartile {i} thin: {bins}"


def test_calibration_window_shape():
    clean = twin.run_calibration(777)  # raises first (red)
    assert clean.shape == (120, 32)


def test_omitted_mag_materializes_in_fault_range():
    from src.config import FAULT_RANGES

    fault = {"id": "F-T", "class": "drift", "origin": "B5", "t0": 150, "dur": 12}
    flist = twin._validate(777, fault)
    assert flist[0].get("mag_sigma") is None
    _, place, _, _, _ = twin._spawn_streams(777)
    specs = twin._materialize(place, flist)
    mlo, mhi = FAULT_RANGES["mag_sigma"]
    assert mlo <= specs[0]["mag"] <= mhi


def test_explicit_mag_preserved():
    fault = {
        "id": "F-T",
        "class": "drift",
        "origin": "B5",
        "t0": 150,
        "dur": 12,
        "mag_sigma": 5.2,
    }
    flist = twin._validate(777, fault)
    assert flist[0]["mag_sigma"] == 5.2
    _, place, _, _, _ = twin._spawn_streams(777)
    specs = twin._materialize(place, flist)
    assert specs[0]["mag"] == 5.2


def test_validate_rejects_t0_before_cal_win():
    for bad_t0 in (0, 119):
        with pytest.raises(ValueError):
            twin._validate(777, dict(_PROBE_FAULT, t0=bad_t0))
    ok = twin._validate(777, dict(_PROBE_FAULT, t0=120))
    assert ok[0]["t0"] == 120


def test_validate_rejects_unknown_origin():
    bad = dict(_PROBE_FAULT, origin="ZZZ-NOPE")
    with pytest.raises(ValueError):
        twin.run_episode(777, bad)
    # No explicitly-global fault class exists (all 7 _FAULT_CLASSES are
    # origin-scoped), so origin=None must also raise.
    missing = {k: v for k, v in _PROBE_FAULT.items() if k != "origin"}
    with pytest.raises(ValueError):
        twin.run_episode(777, missing)
    none_origin = dict(_PROBE_FAULT, origin=None)
    with pytest.raises(ValueError):
        twin.run_episode(777, none_origin)
