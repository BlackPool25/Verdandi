"""Ch2 temperature band characterization (no src/ changes).

Proves twin._sample_signal returns (obs, temp, ar) with temp inside the
TEMP_RANGES band for every class and every machine state, even though the
per-step call site (twin.py:593 ``val, _temp, ar = _sample_signal(...)``)
discards the temp (no temps key on the record).
"""

import numpy as np
import pytest

from src import twin
from src.config import ENVELOPE_SIGMA, TEMP_RANGES

pytestmark = pytest.mark.k5

_STATES = ("RUN", "STARVED", "BLOCKED", "DOWN")

# 2x envelope clamp lives in twin as _CLAMP_SIGMA = 2.0 * ENVELOPE_SIGMA.
_CLAMP_SIGMA = 2.0 * ENVELOPE_SIGMA


def _cfg(cls: str) -> dict[str, object]:
    return {"class": cls, "base": 50.0, "sigma": 1.0, "cycle": 4}


def test_temp_bands_hold_all_classes_all_states() -> None:
    for cls, (tlo, thi) in TEMP_RANGES.items():
        cfg = _cfg(cls)
        assert len(TEMP_RANGES) == 9
        for st in _STATES:
            rng = np.random.default_rng(hash((cls, st)) % (2**32))
            ar = 0.0
            for t in range(25):
                obs, temp, ar = twin._sample_signal(rng, st, t, cfg, ar)
                assert tlo <= temp <= thi, (cls, st, t, temp)
                base = cfg["base"]
                assert isinstance(base, float)
                sigma = cfg["sigma"]
                assert isinstance(sigma, float)
                lo = base - _CLAMP_SIGMA * sigma
                hi = base + _CLAMP_SIGMA * sigma
                assert lo <= obs <= hi, (cls, st, t, obs)


def test_temp_range_key_coverage_is_nine_classes() -> None:
    assert set(TEMP_RANGES) == {
        "feed",
        "form",
        "process",
        "finish",
        "inspect-tail",
        "assembly-kit",
        "assembly-join",
        "test",
        "rework",
    }
