"""MINIPRO-34 Todo 1: couplings flags + schema v3 scaffolding (TDD skeleton).

Scaffolding only — no physics. Flags default OFF; record carries five
26x300 neutral grids + a `couplings` all-False snapshot under schema v3.
"""

import numpy as np
import pytest

from src import twin
from src.config import (
    CODE_VERSION,
    COUPLING_X1A,
    COUPLING_X1B,
    COUPLING_X2,
    COUPLING_X3,
    COUPLING_X4,
    MACHINES,
    TEMP_RANGES,
    TWIN_SCHEMA,
    check_couplings,
)

pytestmark = pytest.mark.k1

_ALL = (COUPLING_X1A, COUPLING_X1B, COUPLING_X2, COUPLING_X3, COUPLING_X4)
_ALL_OFF = {"X1A": False, "X1B": False, "X2": False, "X3": False, "X4": False}


def test_flags_default_off():
    for d in _ALL:
        assert d["enabled"] is False


def test_coupling_validator_bites():
    live = {
        "X1A": dict(COUPLING_X1A),
        "X1B": dict(COUPLING_X1B),
        "X2": dict(COUPLING_X2),
        "X3": dict(COUPLING_X3),
        "X4": dict(COUPLING_X4),
    }
    check_couplings(live)  # the shipped table validates clean
    with pytest.raises(ValueError):
        check_couplings({**live, "X9": {"enabled": False}})
    with pytest.raises(ValueError):
        check_couplings({**live, "X1A": {**live["X1A"], "bogus_key": 1.0}})
    with pytest.raises(ValueError):
        check_couplings({**live, "X1A": {**live["X1A"], "alpha_cu": -1.0}})
    with pytest.raises(ValueError):
        check_couplings({**live, "X1B": {**live["X1B"], "e_trip": 0.0}})


def test_schema_v3_present():
    assert TWIN_SCHEMA == 3
    assert CODE_VERSION == "twin-3.0.0-xcouplings"
    rec = twin.run_episode(777, None)
    assert rec["schema_version"] == 3
    assert rec["code_version"] == "twin-3.0.0-xcouplings"
    for key in ("therm", "wear", "force", "inrush", "life"):
        grid = rec[key]
        assert len(grid) == 26
        assert all(len(row) == 300 for row in grid)
    assert rec["couplings"] == dict(_ALL_OFF)
    # Neutral-when-OFF: therm = band midpoint, wear/force/inrush/life zero-ish.
    order = sorted(MACHINES, key=lambda m: twin.MACHINE_INDEX[m])
    for i, name in enumerate(order):
        tlo, thi = TEMP_RANGES[MACHINES[name]["class"]]
        mid = (tlo + thi) / 2.0
        assert rec["therm"][i] == [mid] * 300
        assert rec["wear"][i] == [0.0] * 300
        assert rec["inrush"][i] == [0.0] * 300
        assert rec["life"][i] == [0.0] * 300
        for t in range(300):
            want = 1.0 if rec["states"][i][t] == "RUN" else 0.0
            assert rec["force"][i][t] == want


def test_couplings_override_snapshot():
    rec = twin.run_episode(777, None, couplings={**_ALL_OFF, "X1A": True, "X3": True})
    assert rec["couplings"] == {
        "X1A": True,
        "X1B": False,
        "X2": False,
        "X3": True,
        "X4": False,
    }


def test_calibration_all_off():
    clean = twin.run_calibration(777)
    assert clean.shape == (120, 26)
    rec = twin.run_episode(
        777,
        None,
        enable_natural_breakdown=False,
        couplings=dict(_ALL_OFF),
    )
    assert np.array_equal(clean, np.asarray(rec["obs"], dtype=float)[:, :120].T)
