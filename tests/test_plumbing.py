"""Plumbing audit tests: carrier reachability via paired sim runs."""

import numpy as np


def _fault():
    return {"origin": "B2", "class": "breakdown", "t0": 130, "dur": 40}


def test_breakdown_carrier_fires():
    from src.plumbing import CARRIERS, paired_z

    assert set(CARRIERS) >= {"loss", "quality", "drift", "bias", "spike", "breakdown"}
    out = paired_z(_fault(), seed=0, carriers=CARRIERS["breakdown"], k=3.0)
    assert out["fired"] is True and out["tick"] - 130 < 40


def test_determinism():
    from src.plumbing import CARRIERS, paired_z

    a = paired_z(_fault(), 0, CARRIERS["breakdown"], 3.0)
    b = paired_z(_fault(), 0, CARRIERS["breakdown"], 3.0)
    assert a == b


def test_monitor_set_nonempty_per_family():
    from src.plumbing import CARRIERS

    for fam in ("loss", "quality", "drift", "bias", "spike"):
        assert len(CARRIERS[fam]) > 0, fam
