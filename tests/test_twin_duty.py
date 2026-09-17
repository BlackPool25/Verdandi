"""T9 duty-cycle gates (MINIPRO-33 Todo 6 + owner-approved option C retime).

Scope (normative, plan Todo 6 as amended by owner option C 2026-09-17):
clean episodes, enable_natural_breakdown=True, seeds [777,1234,999,42,2026],
T=300. Plant-mean over 24 machines (B7S spare + RWK0 rework loop excluded
via STANDBY_EXCLUDED — redundancy/rework-by-design, scope change recorded
for SIM_SPEC Todo 10): RUN share >= 80%, STARVED share <= 15%, BLOCKED
share reported (no hard cap — the pile-up bound covers it); xfer_open == 0
at T via cap-aware spawn guard + land-grace drain (AGV_DRAIN_GRACE=8;
env obs loops still end at T, obs shapes intact); pile-up bound: no gap
buffer at cap for >= 30 consecutive steps while its downstream machine is
STARVED in the same window. TAKT5 Table 3.1 retime + AGV 2->3 (see
src/config.py) move RUN .64->.85+ / STARVED .34->.13-.

Traceability: MINIPRO-24 T9 bounds; src/twin.py duty_cycle(record).
"""

import pytest

from src import twin

pytestmark = pytest.mark.k2

_SEEDS = [777, 1234, 999, 42, 2026]
_T = 300

_RUN_MIN = 0.80
_STARVED_MAX = 0.15


def _clean(seed):
    rec = twin.run_episode(seed, None, enable_natural_breakdown=True)
    assert rec["T"] == _T
    return twin.duty_cycle(rec)  # raises first (red: helper not implemented)


@pytest.mark.parametrize("seed", _SEEDS)
def test_duty_run_share(seed):
    assert _clean(seed)["run_share"] >= _RUN_MIN


@pytest.mark.parametrize("seed", _SEEDS)
def test_duty_starved_share(seed):
    assert _clean(seed)["starved_share"] <= _STARVED_MAX


@pytest.mark.parametrize("seed", _SEEDS)
def test_duty_blocked_reported(seed):
    blk = _clean(seed)["blocked_share"]
    assert 0.0 <= blk <= 1.0  # reported, no hard cap


@pytest.mark.parametrize("seed", _SEEDS)
def test_duty_xfer_drained(seed):
    assert _clean(seed)["xfer_open"] == 0


@pytest.mark.parametrize("seed", _SEEDS)
def test_duty_no_pileup(seed):
    assert _clean(seed)["pileup_violations"] == []
