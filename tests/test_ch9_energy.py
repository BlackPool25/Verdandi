"""CH9 header-only energy tests (Todo W4, TDD RED-first).

Header contract: flow_stats["energy"] = {sum_kVAh: float, per_unit:
float|None, note: str, unit: "kVAh-apparent", step_seconds: 1}.
E_step = sqrt(3)*400*I_clamped*STEP_SECONDS/3600 (apparent index,
relative-only, no PF). packaged == 0 => per_unit None, note
"packaged==0". Sum uses I_clamped (negatives contribute 0). NO per-tick
series, NO kWh label, NO RNG in the CH9 path.
"""

import inspect
import math

from src import twin
from src.config import STEP_SECONDS, VOLT


def _expected_sum(currents):
    return sum(
        math.sqrt(3.0) * VOLT * (max(0.0, i)) * STEP_SECONDS / 3600.0
        for row in currents
        for i in row
    )


def test_ch9_null_guard_and_clamp_packaged_zero():
    hdr = twin._energy_header([[5.0] * 3 for _ in range(2)], 0)
    assert isinstance(hdr["sum_kVAh"], float)
    assert hdr["per_unit"] is None
    assert hdr["note"] == "packaged==0"
    assert hdr["sum_kVAh"] > 0.0


def test_ch9_null_guard_and_clamp_sum_uses_I_clamped():
    currents = [[-5.0, 4.0], [0.0, 10.0]]
    hdr = twin._energy_header(currents, 2)
    assert math.isclose(hdr["sum_kVAh"], _expected_sum(currents), rel_tol=1e-9)
    assert hdr["per_unit"] == hdr["sum_kVAh"] / 2
    # Negative raw current contributes nothing (clamped leg).
    assert math.isclose(
        hdr["sum_kVAh"], _expected_sum([[0.0, 4.0], [0.0, 10.0]]), rel_tol=1e-9
    )


def test_ch9_null_guard_and_clamp_header_shape_unit_step():
    hdr = twin._energy_header([[1.0]], 1)
    assert set(hdr) == {"sum_kVAh", "per_unit", "note", "unit", "step_seconds"}
    assert hdr["unit"] == "kVAh-apparent"
    assert "kWh" not in hdr["unit"]
    assert hdr["step_seconds"] == STEP_SECONDS == 1
    assert "series" not in hdr and "per_tick" not in hdr


def test_ch9_null_guard_and_clamp_no_rng_in_path():
    src = inspect.getsource(twin._energy_header)
    for token in ("random", "default_rng", "uniform", "normal", "choice", "shuffle"):
        assert token not in src, token


def test_ch9_null_guard_and_clamp_clean_episode_header():
    rec = twin.run_episode(7, None)
    energy = rec["flow_stats"]["energy"]
    assert energy["unit"] == "kVAh-apparent"
    assert energy["step_seconds"] == 1
    assert isinstance(energy["sum_kVAh"], float) and energy["sum_kVAh"] > 0.0
    assert energy["per_unit"] is not None and energy["per_unit"] > 0.0
    assert math.isclose(
        energy["sum_kVAh"], _expected_sum(rec["currents"]), rel_tol=1e-9
    )
    assert rec["flow_stats"]["packaged"] > 0
    assert "energy_series" not in rec["flow_stats"]
    assert "energy" in twin._DIGEST_SCRUB_FLOW_KEYS
