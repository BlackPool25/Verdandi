"""Topology-A serial rewire pins (MINIPRO-33 Todo 2, TDD).

Red-first: every test here FAILS on the 32-machine twin (dropped names
present, rewired gaps absent) and PASSES after the _LINES/_TAILS/
_line_edges/run_episode rewire. Normative roster: 26 machines, 26
buffers; interiors A3-A6/B3-B6/C3-C5 + single B7 + ASM12 retired.
"""

import pytest

from src import twin
from src.config import BUFFERS, MACHINE_INDEX, MACHINES, N_BUFFERS, N_MACHINES

pytestmark = pytest.mark.k2

_DROPPED = (
    "A3",
    "A4",
    "A5",
    "A6",
    "B3",
    "B4",
    "B5",
    "B6",
    "C3",
    "C4",
    "C5",
    "B7",
)

_EXPECTED_LINES = (
    "A0",
    "A1",
    "A2",
    "A7",
    "A8",
    "A9",
    "B0",
    "B1",
    "B2",
    "B7P",
    "B7S",
    "B8",
    "B9",
    "C0",
    "C1",
    "C2",
    "C6",
    "C7",
    "PKG0",
    "PKG1",
    "PKG2",
    "INSP0",
)


def test_lines_topology_a_roster():
    assert tuple(twin._LINES) == _EXPECTED_LINES
    for name in _DROPPED:
        assert name not in twin._LINES
    assert "ASM12" not in twin._LINES


def test_tails_extended_with_pkg_sinks():
    assert tuple(twin._TAILS) == ("A9", "B9", "C7", "PKG1", "PKG2")


def test_line_edges_rewired_gaps():
    edges = twin._line_edges()
    assert edges["A2"][1] == "A27"
    assert edges["C2"][1] == "C26"
    assert edges["B7P"] == ("B2B7P", "B7PB8")
    assert edges["B7S"] == ("B2B7S", "B7SB8")
    assert edges["INSP0"] == ("INSP01", "INSP02")
    assert edges["PKG1"] == ("PKG01", None)
    assert edges["PKG2"] == ("PKG02", None)


def test_line_edges_fork_join():
    edges = twin._line_edges()
    assert edges["B2"][1] == ("B2B7P", "B2B7S")
    assert edges["B8"][0] == ("B7PB8", "B7SB8")
    assert edges["C7"][1] == ("_C7TAIL", "C7PKG")
    assert edges["PKG0"] == ("C7PKG", ("PKG01", "PKG02"))


def test_line_edges_cover_lines_only():
    edges = twin._line_edges()
    assert set(edges) == set(twin._LINES)
    for name in ("ASM0", "ASM1", "ASM2", "RWK0"):
        assert name not in edges


def test_line_edges_no_retired_names():
    import re

    edges = twin._line_edges()
    blob = repr(edges)
    for name in _DROPPED + ("ASM12",):
        assert re.search(rf"'{name}'", blob) is None, name
    for up, down in edges.values():
        for key in up if isinstance(up, tuple) else (up,):
            assert key is None or key in BUFFERS or key == "_C7TAIL"
        for key in down if isinstance(down, tuple) else (down,):
            assert key is None or key in BUFFERS or key == "_C7TAIL"


def test_episode_topology_a_shape():
    rec = twin.run_episode(777, None)
    assert rec["T"] == 300
    assert len(rec["obs"]) == N_MACHINES == 26
    assert all(len(row) == 300 for row in rec["obs"])
    assert len(rec["buffers"]) == N_BUFFERS == 26
    assert all(len(row) == 300 for row in rec["buffers"])
    for name in ("PKG0", "PKG1", "PKG2", "INSP0", "B7P", "B7S"):
        assert name in MACHINE_INDEX and name in MACHINES
    for name in _DROPPED:
        assert name not in MACHINE_INDEX
    assert "packaged" in rec["flow_stats"]
    assert sum(rec["throughput"][MACHINE_INDEX["INSP0"]]) > 0
    assert sum(rec["throughput"][MACHINE_INDEX["B7P"]]) > 0


def test_dropped_origin_rejected():
    with pytest.raises(ValueError):
        twin.run_episode(777, {"origin": "B5", "class": "drift", "t0": 150, "dur": 12})
