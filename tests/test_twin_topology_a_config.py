"""Topology-A config roster tests (MINIPRO-33 Todo 1, TWIN_SCHEMA v2).

Pure-config scope ONLY: no twin import, no run_episode (episode rewire is
Todo 2). Table 3.1 values live in src/config.py; this file asserts shape,
never duplicates coefficients except the six normative new rows' full-row
equality (checked field-by-field against config, not re-declared).
"""

import pytest

from src.config import (
    BUFFERS,
    CODE_VERSION,
    INSPECT_DELAY_STEPS,
    MACHINE_INDEX,
    MACHINES,
    N_BUFFERS,
    N_MACHINES,
    TWIN_SCHEMA,
    check_config,
)

pytestmark = pytest.mark.k1

_EXPECTED_ORDER = (
    "A0", "A1", "A2", "A7", "A8", "A9",
    "B0", "B1", "B2", "B7P", "B7S", "B8", "B9",
    "C0", "C1", "C2", "C6", "C7",
    "PKG0", "PKG1", "PKG2",
    "ASM0", "ASM1", "INSP0", "ASM2", "RWK0",
)

_EXPECTED_CAPS = {
    "A01": 20, "A12": 20, "A27": 25, "A78": 15, "A89": 15,
    "B01": 20, "B12": 20, "B2B7P": 25, "B2B7S": 25, "B7PB8": 25,
    "B7SB8": 25, "B89": 15,
    "C01": 20, "C12": 20, "C26": 25, "C67": 15,
    "ASM01": 25, "INSP01": 25, "INSP02": 25, "GA9": 15, "GB9": 15,
    "C7PKG": 15, "PKG01": 15, "PKG02": 15,
    "RWK_RET": 10, "SBUF": 30,
}

_DROPPED = (
    "A3", "A4", "A5", "A6", "B3", "B4", "B5", "B6", "B7", "C3", "C4", "C5",
)


def test_counts_26():
    assert len(MACHINES) == N_MACHINES == 26
    assert len(BUFFERS) == N_BUFFERS == 26


def test_machine_index_literal_order():
    assert tuple(MACHINE_INDEX) == _EXPECTED_ORDER
    assert [MACHINE_INDEX[n] for n in _EXPECTED_ORDER] == list(range(26))
    assert set(MACHINE_INDEX) == set(MACHINES)


def test_dropped_machines_absent():
    for name in _DROPPED:
        assert name not in MACHINES
        assert name not in MACHINE_INDEX


def test_buffer_roster_caps():
    assert set(BUFFERS) == set(_EXPECTED_CAPS)
    for name, cap in _EXPECTED_CAPS.items():
        assert BUFFERS[name] == cap, name


def test_schema_version_pins():
    assert TWIN_SCHEMA == 2
    assert CODE_VERSION == "twin-2.1.0-topology-A"
    assert INSPECT_DELAY_STEPS == 3


def test_new_table31_rows():
    assert MACHINES["PKG0"] == {
        "class": "assembly-kit", "base": 65.0, "sigma": 1.3, "cycle": 5,
        "mttf": 1000, "mttr": 12, "buffer_cap": 25, "transit": 2,
    }
    for name in ("PKG1", "PKG2"):
        assert MACHINES[name] == {
            "class": "finish", "base": 55.0, "sigma": 1.1, "cycle": 4,
            "mttf": 1200, "mttr": 10, "buffer_cap": 15, "transit": None,
        }, name
    for name in ("B7P", "B7S"):
        assert MACHINES[name] == {
            "class": "process", "base": 70.0, "sigma": 1.5, "cycle": 6,
            "mttf": 800, "mttr": 20, "buffer_cap": 25, "transit": 3,
        }, name
    assert MACHINES["INSP0"] == {
        "class": "test", "base": 45.0, "sigma": 2.0, "cycle": 2,
        "mttf": 1200, "mttr": 10, "buffer_cap": 25, "transit": 2,
    }


def test_pkg_tails_are_sinks():
    assert MACHINES["PKG1"]["transit"] is None
    assert MACHINES["PKG2"]["transit"] is None


def test_check_config_guard_alive():
    with pytest.raises(ValueError):
        check_config([("A0", {"buffer_cap": 0})], [("B0", 1)])
