"""MINIPRO-34 Todo 1: couplings flags + schema v3 scaffolding (TDD skeleton).

Scaffolding only — no physics. Flags default OFF; record carries five
26x300 neutral grids + a `couplings` all-False snapshot under schema v3.
"""

import itertools

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


# ---- Todo 2: X1a winding I2R feedback (C4 probation battery) ----

_X1A_ON = {"X1A": True, "X1B": False, "X2": False, "X3": False, "X4": False}
_X1A_SEEDS = (777, 1234, 999, 42, 2026)
_X1A_PROCESS_MACHINES = ("A2", "A7", "B2", "B7P", "B7S", "C2", "C6")
_X1A_OFF_DIGEST_777 = "b2cead18b5747d5a1b1bacc6ea4e42aca59b64f6591c5853f19b545903bad876"
_X1A_BAND_MARGIN = 2.0


def _x1a_slice():
    """14-fault probation slice: 7 process machines x {drift, bias}."""
    faults = []
    for name in _X1A_PROCESS_MACHINES:
        for cls in ("drift", "bias"):
            faults.append(
                {
                    "class": cls,
                    "origin": name,
                    "t0": 150,
                    "dur": 25,
                    "mag_sigma": 2.0,
                }
            )
    return faults


def _x1a_overload_flag(rec):
    """Episode-level overload flag: any process-machine therm row clears band-top."""
    order = sorted(MACHINES, key=lambda m: twin.MACHINE_INDEX[m])
    for i, name in enumerate(order):
        if MACHINES[name]["class"] != "process":
            continue
        thi = TEMP_RANGES[MACHINES[name]["class"]][1]
        if max(rec["therm"][i]) > thi + _X1A_BAND_MARGIN:
            return True
    return False


def _f1(y_true, y_pred):
    tp = sum(1 for a, b in zip(y_true, y_pred) if a and b)
    fp = sum(1 for a, b in zip(y_true, y_pred) if b and not a)
    fn = sum(1 for a, b in zip(y_true, y_pred) if a and not b)
    den = 2 * tp + fp + fn
    return 2 * tp / den if den else 0.0


def test_battery_x1a_c4_probation():
    faults = _x1a_slice()
    assert len(faults) == 14
    assert len(_X1A_SEEDS) == 5
    yt_all, on_all, off_all, per_seed = [], [], [], []
    for seed in _X1A_SEEDS:
        yt = [True] * len(faults)
        po = [
            _x1a_overload_flag(twin.run_episode(seed, dict(f), couplings=dict(_X1A_ON)))
            for f in faults
        ]
        pf = [
            _x1a_overload_flag(
                twin.run_episode(seed, dict(f), couplings=dict(_ALL_OFF))
            )
            for f in faults
        ]
        per_seed.append((seed, _f1(yt, po), _f1(yt, pf)))
        yt_all += yt
        on_all += po
        off_all += pf
    agg_on, agg_off = _f1(yt_all, on_all), _f1(yt_all, off_all)
    assert len(yt_all) == 70
    assert agg_on - agg_off >= 0.03, f"X1a bar missed: per-seed={per_seed}"


def test_x1a_overload_drifts():
    fault = {"class": "drift", "origin": "B2", "t0": 150, "dur": 25, "mag_sigma": 2.0}
    off = twin.run_episode(777, dict(fault), couplings=dict(_ALL_OFF))
    on = twin.run_episode(777, dict(fault), couplings=dict(_X1A_ON))
    i = twin.MACHINE_INDEX["B2"]
    mid = sum(TEMP_RANGES["process"]) / 2.0
    assert off["therm"][i] == [mid] * 300
    row = on["therm"][i]
    assert all(b - a >= -1e-9 for a, b in itertools.pairwise(row))
    assert row[-1] > row[0] + 20.0
    assert max(row) > TEMP_RANGES["process"][1] + _X1A_BAND_MARGIN
    assert twin.replay_digest(on) != twin.replay_digest(off)


def test_x1a_off_digest_stable():
    rec = twin.run_episode(777, None, couplings=dict(_ALL_OFF))
    assert twin.replay_digest(rec) == _X1A_OFF_DIGEST_777


def test_therm_step_first_order():
    amb, band, gain, tau = 25.0, 70.0, 10.0, 12.0
    cur, load, eff, heat = 77.5, 1.0, 1.7, 0.0
    want = cur + ((amb + band * load + gain * eff * eff + heat) - cur) / tau
    assert twin._therm_step(cur, load, eff, heat, amb, band, gain, tau) == want
    assert twin._therm_step(200.0, 1.0, 1.0, 0.0, amb, band, gain, tau) < 200.0


def test_x1a_heat_source_sensitivity(monkeypatch):
    monkeypatch.setitem(twin.COUPLING_X1A["k_cu"], "process", 0.0)
    rec = twin.run_episode(
        777,
        {"class": "drift", "origin": "B2", "t0": 150, "dur": 25, "mag_sigma": 2.0},
        couplings=dict(_X1A_ON),
    )
    i = twin.MACHINE_INDEX["B2"]
    assert max(rec["therm"][i]) <= TEMP_RANGES["process"][1] + _X1A_BAND_MARGIN
