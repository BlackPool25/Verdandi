"""_C7TAIL off-roster store visible via flow_stats; 26-row shape contract held."""

import pytest

from src import twin
from src.config import BUFFERS, MACHINES

pytestmark = pytest.mark.k5

_SEED = 777
_T = 300

_DELAY_A5 = {
    "id": "F-T2-delay",
    "class": "delay",
    "origin": "A2",
    "t0": 150,
    "dur": 15,
    "mag_sigma": 0.0,
    "extra": {"d": 5},
}


def test_c7tail_off_roster_visible_via_flow_stats():
    rec = twin.run_episode(_SEED, _DELAY_A5)
    assert len(rec["buffers"]) == 26
    assert all(len(row) == _T for row in rec["buffers"])
    store_final = rec["flow_stats"]["store_final"]
    assert "_C7TAIL" in store_final
    assert 0 <= rec["flow_stats"]["c7tail"] <= 15
    assert 0 <= store_final["_C7TAIL"] <= MACHINES["C7"]["buffer_cap"]


def test_c7tail_cap_pinned_15_off_roster():
    assert MACHINES["C7"]["buffer_cap"] == 15
    assert (
        MACHINES["C7"]["mttr"] == 8
    )  # repair scalar, not the cap (Copilot :1052 misread)
    assert "_C7TAIL" not in BUFFERS  # dedicated store, never the C67 gap
    assert (
        BUFFERS["C67"] == 15
    )  # distinct gap store; sharing it would deadlock C6 vs C7
    assert len(BUFFERS) == 26
    rec = twin.run_episode(_SEED, _DELAY_A5)
    buf_order = list(BUFFERS)
    c67 = rec["buffers"][buf_order.index("C67")]
    assert len(c67) == _T
    assert all(0 <= lvl <= BUFFERS["C67"] for lvl in c67)
