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

import pathlib

import pytest

from src import twin

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
    assert set(rec) == {
        "seed", "T", "cal_win", "obs", "states",
        "buffers", "throughput", "events", "sbuf_stats", "flow_stats",
        "agv_waits", "parts", "faults",
    }


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
        for (t0a, da), (t0b, _db) in zip(windows, windows[1:]):
            assert t0b - (t0a + da) >= 5


def test_cal_win_zero_faults_before_120():
    faults = twin.build_faults(777)  # raises first (red)
    assert all(f["t0"] >= 120 for f in faults)


def test_calibration_window_shape():
    clean = twin.run_calibration(777)  # raises first (red)
    assert clean.shape == (120, 32)
