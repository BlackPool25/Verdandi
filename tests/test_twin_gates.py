"""TDD red step (T3): coverage + determinism + wall/quarantine gates.

TC-006 (TST-003, TEST_CASES.md:112-123): validate_coverage(manifest, oracle)
pure-function gate over the partitions(5) x channels(7) x classes(7) matrix.
TC-008 (TST-006, TEST_CASES.md:149-158): 5 faults x 5 seeds, replay_hash
sha256 identical, diverge=0. TC-009 wall tripwire (TEST_CASES.md:160-170):
extrapolation + exit-2 trigger on fixture numbers only. Quarantine
(no spike/torch/FactorySimPy/0.45, torch not importable) and
no-restart-strings greps.

RED SPLIT: behavioral tests (coverage/determinism/wall) MUST fail with
NotImplementedError until T5/T7/T8 land — each one invokes a T1 stub first
(same "raises first" pattern as tests/test_twin_schema.py) because the
T8-owned entry points (validate_coverage, check_wall_tripwire) do not exist
yet. Grep tests (test_quarantine_*, test_clearance_*) are green-from-start:
the stubs contain no banned strings. No F1/AC@1/flip/grounding thresholds
anywhere in this file.
"""

import copy
import hashlib
import json
import pathlib
import re
import subprocess
import sys

import pytest

from src import twin

_SRC_DIR = pathlib.Path(__file__).resolve().parent.parent / "src"

# TC-006 scope: 5 partition groups (TEST_CASES.md:116: Line-A/B/C, assembly
# cell, rework loop) x 7 channels (SIM_SPEC sect 8) x 7 classes (SIM_SPEC
# sect 5). T8 runs validate_coverage on the real manifest.
PARTITIONS = ["line-A", "line-B", "line-C", "cell", "rework"]
CHANNELS = [
    "vibration", "temperature", "throughput", "quality",
    "state", "buffer", "event",
]
CLASSES = ["spike", "drift", "bias", "delay", "loss", "breakdown", "quality"]

# INDEPENDENT oracle: representative-machine subset per SIM_SPEC sect 5,
# including the running example F-21 (drift, B5, t0=150, dur=12, mag=5.2σ;
# SIM_SPEC:251). Kept as a literal constant so T8 cannot fit the validator
# to the manifest under test.
ORACLE_REP_FAULTS = [
    {"id": "F-06", "class": "spike", "origin": "A0",
     "t0": 150, "dur": 10, "mag_sigma": 5.0},
    {"id": "F-21", "class": "drift", "origin": "B5",
     "t0": 150, "dur": 12, "mag_sigma": 5.2},
    {"id": "F-22", "class": "bias", "origin": "B6",
     "t0": 160, "dur": 12, "mag_sigma": 5.0},
    {"id": "F-23", "class": "delay", "origin": "B4",
     "t0": 170, "dur": 12, "extra": {"d": 4}},
    {"id": "F-24", "class": "loss", "origin": "B7",
     "t0": 180, "dur": 12, "extra": {"drop_rate": 0.2}},
    {"id": "F-25", "class": "breakdown", "origin": "B2",
     "t0": 190, "dur": 12, "extra": {"mttr_mult": 2}},
    {"id": "F-26", "class": "quality", "origin": "B9",
     "t0": 200, "dur": 12, "extra": {"reject_rate": 0.25}},
]


def _full_manifest():
    """5-row fixture: one row per partition group, each row declaring full
    channel x class coverage plus its fault ids (union covers the oracle)."""
    return [
        {"partition": "line-A", "machine": "A0",
         "channels": list(CHANNELS), "classes": list(CLASSES),
         "fault_ids": ["F-06"]},
        {"partition": "line-B", "machine": "B5",
         "channels": list(CHANNELS), "classes": list(CLASSES),
         "fault_ids": ["F-21", "F-22", "F-23", "F-24", "F-25"]},
        {"partition": "line-C", "machine": "C2",
         "channels": list(CHANNELS), "classes": list(CLASSES),
         "fault_ids": ["F-07"]},
        {"partition": "cell", "machine": "ASM1",
         "channels": list(CHANNELS), "classes": list(CLASSES),
         "fault_ids": ["F-08"]},
        {"partition": "rework", "machine": "RWK0",
         "channels": list(CHANNELS), "classes": list(CLASSES),
         "fault_ids": ["F-26"]},
    ]


def test_coverage_full_matrix_zero_empty():
    twin.build_faults(777)  # raises first (red); validator target below
    gaps = twin.validate_coverage(_full_manifest(), ORACLE_REP_FAULTS)
    assert gaps == []


def test_coverage_matrix_dimensions():
    twin.build_faults(777)  # raises first (red); validator target below
    gaps = twin.validate_coverage(_full_manifest(), ORACLE_REP_FAULTS)
    assert gaps == []
    assert (len(PARTITIONS), len(CHANNELS), len(CLASSES)) == (5, 7, 7)


def test_coverage_rep_subset_oracle():
    twin.build_faults(777)  # raises first (red); validator target below
    gaps = twin.validate_coverage(_full_manifest(), ORACLE_REP_FAULTS)
    assert gaps == []
    assert any(f["id"] == "F-21" and f["origin"] == "B5"
               and f["t0"] == 150 and f["dur"] == 12
               and f["mag_sigma"] == 5.2 for f in ORACLE_REP_FAULTS)


def test_coverage_planted_empty_cell_fails():
    """Anti-vacuity: a manifest with one planted hole must NOT validate."""
    twin.build_faults(777)  # raises first (red); validator target below
    holed = _full_manifest()
    holed[1]["channels"] = [c for c in CHANNELS if c != "event"]
    gaps = twin.validate_coverage(holed, ORACLE_REP_FAULTS)
    assert gaps != []
    assert any("line-B" in str(g) and "event" in str(g) for g in gaps)


def test_coverage_malformed_row_rejected():
    """Malformed manifest row (missing key) must FAIL, never pass silently."""
    twin.build_faults(777)  # raises first (red); validator target below
    bad = [{"partition": "line-A", "machine": "A0"}]
    with pytest.raises((ValueError, KeyError)):
        twin.validate_coverage(bad, ORACLE_REP_FAULTS)


# TC-008: 5 representative faults (one per base class incl. F-06) x 5 seeds.
_DETERMINISM_FAULTS = [
    {"id": "F-06", "class": "spike", "origin": "A0",
     "t0": 150, "dur": 10, "mag_sigma": 5.0},
    {"id": "F-21", "class": "drift", "origin": "B5",
     "t0": 150, "dur": 12, "mag_sigma": 5.2},
    {"id": "F-12", "class": "bias", "origin": "A4",
     "t0": 160, "dur": 12, "mag_sigma": 5.0},
    {"id": "F-14", "class": "delay", "origin": "A5",
     "t0": 170, "dur": 12, "extra": {"d": 4}},
    {"id": "F-16", "class": "loss", "origin": "A6",
     "t0": 180, "dur": 12, "extra": {"drop_rate": 0.2}},
]
_DETERMINISM_SEEDS = [777, 1234, 999, 42, 2026]

# Canonical replay hash per Scope: sorted keys, repr floats (json default),
# wall/clock fields excluded.
_WALLCLOCK_KEYS = {"wall_s", "timestamp", "clock", "elapsed"}


def _canonical_hash(record):
    scrubbed = {k: v for k, v in record.items() if k not in _WALLCLOCK_KEYS}
    return hashlib.sha256(
        json.dumps(scrubbed, sort_keys=True).encode()).hexdigest()


def test_determinism_replay_hash_identical():
    for fault in _DETERMINISM_FAULTS:
        for seed in _DETERMINISM_SEEDS:
            rec_a = twin.run_episode(seed, copy.deepcopy(fault))
            rec_b = twin.run_episode(seed, copy.deepcopy(fault))
            assert _canonical_hash(rec_a) == _canonical_hash(rec_b)


def test_determinism_zero_diverge():
    for fault in _DETERMINISM_FAULTS:
        for seed in _DETERMINISM_SEEDS:
            rec_a = twin.run_episode(seed, copy.deepcopy(fault))
            rec_b = twin.run_episode(seed, copy.deepcopy(fault))
            diverge = 0 if rec_a == rec_b else 1
            assert diverge == 0


def test_wall_tripwire_projection():
    # Fixture numbers ONLY (extrapolation math + exit-2 trigger logic).
    # The real wall budget is MEASURED at T5/T8, never arithmetic proof here.
    twin.run_calibration(777)  # raises first (red); tripwire target below
    under = twin.check_wall_tripwire([100.0, 110.0, 90.0, 80.0], budget=600.0)
    assert under == (380.0, False)
    over = twin.check_wall_tripwire([200.0, 200.0, 200.0, 200.0], budget=600.0)
    assert over == (800.0, True)  # trip -> runner exits 2


_QUARANTINE_PATTERN = re.compile(r"spike|torch|FactorySimPy|0\.45")
_RESTART_PATTERN = re.compile(r"clearance|restart.authority")


def _grep_src(pattern):
    hits = []
    for path in sorted(_SRC_DIR.rglob("*")):
        if path.is_file() and not path.name.startswith("."):
            try:
                text = path.read_text(errors="strict")
            except (UnicodeDecodeError, OSError):
                continue
            for n, line in enumerate(text.splitlines(), 1):
                if pattern.search(line):
                    hits.append(f"{path.name}:{n}:{line.strip()}")
    return hits


def test_quarantine_no_banned_strings():
    assert _grep_src(_QUARANTINE_PATTERN) == []
    proc = subprocess.run(
        [sys.executable, "-c", "import torch"], capture_output=True)
    assert proc.returncode != 0


def test_clearance_no_restart_strings():
    assert _grep_src(_RESTART_PATTERN) == []
