"""Conservation exact-balance (topology-A embodiment, port of upstream proof).

Upstream (32-machine, 8e0566b test_duty_conservation) proved:
  line_created == 3*sunk + stores + kit + held + 3*held_asm + xfer + sbuf.
The literal form does NOT balance on topology-A (RED: diffs -3,-3,-1,-9,-1
on the 5 duty seeds) — embodiment changed, so the equation is re-derived
from src/twin.py here, never assumed from the 32-line formula:

- sunk/scrapped co-increment on ONE part (twin _asm_mid_process/_rwk0_process
  scrap sinks) so scrapped ⊆ sunk — never add both.
- Each sunk assembly, each ASM-stage holding (held_asm0_batch/held_asm12/
  held_rwk0), and each ASM01/INSP01/INSP02/RWK_RET store slot embodies an
  A+B+C triple, hence x3.
- Line-gap stores, GA9/GB9 tail buffers, _C7TAIL, kit_A/B/C, main-line held,
  xfer_open (AGV drains tails/SBUF only — singles), and SBUF final hold
  single line parts (x1).
- C7 broadcast (_line_process C7 branch) stages the original to _C7TAIL and
  mints a COPY to C7PKG; copies flow C7PKG->PKG0->PKG01/02->PKG1/2->packaged
  and never reach kit/SBUF/AGV. So C7PKG/PKG01/PKG02 stores, PKG0/1/2 held
  parts, and the packaged sink form a closed copy sub-plant: excluded from
  BOTH sides (copies-made is unlogged; packaged == copies-made minus
  copy-stock cancels exactly). rejected/reworked are flows, absent from a
  stock census.
- INSP0 sits in _LINES but pulls INSP01 assemblies — its held part embodies
  a triple (x3), split out from the x1 held_line aggregate.
- held split (held_insp0/held_pkg/held_main) is read via a call-time spy on
  twin._line_process that records the shared dict and delegates untouched:
  probe-verified digest-identical with/without the spy (777-clean
  652fba4f… both ways), so no RNG/draw/condition path is touched and no
  twin change was needed.

Deliberately NOT ported from the upstream test body: rework passes<=2
(lives in tests/test_twin_flow.py::test_rework_passes_capped_and_scrap)
and the clean-SBUF diverted==drained pin (covered by duty xfer + flow
drain tests) — no duplication.

Proof record (scratch probe, pre-assert): exact diff 0 on 777/1234/999/42/
2026 clean AND 777 F-21; naive-literal diffs -3/-3/-1/-9/-1/+0. No real drop
found — twin conserves; test-only deliverable, zero twin change.
"""

import copy
from unittest import mock

import pytest

from src import twin
from src.config import MACHINE_INDEX

pytestmark = pytest.mark.k2

_SEEDS = (777, 1234, 999, 42, 2026)

_F21_B2 = {
    "id": "F-21",
    "class": "drift",
    "origin": "B2",
    "t0": 150,
    "dur": 12,
    "mag_sigma": 5.2,
}

# Assembly-triple stores (x3): ASM12 retired -> INSP01/INSP02 stage ASM
# assemblies between ASM1/INSP0/ASM2; RWK_RET holds rejected assemblies.
_ASM_STORES = ("ASM01", "INSP01", "INSP02", "RWK_RET")
# Packaging-copy sub-plant (excluded both sides — see module docstring).
_PKG_STORES = ("C7PKG", "PKG01", "PKG02")
_PKG_MACHINES = ("PKG0", "PKG1", "PKG2")


def _run_with_held(seed, fault=None):
    """run_episode plus end-state held split, via a delegating call-time spy."""
    captured = {}
    orig = twin._line_process

    def _spy(env, spec, shared):
        captured[spec["name"]] = shared
        return orig(env, spec, shared)

    with mock.patch.object(twin, "_line_process", _spy):
        rec = twin.run_episode(seed, copy.deepcopy(fault) if fault else None)
    shared = next(iter(captured.values()))
    held = shared["held"]
    held_insp0 = 1 if held[MACHINE_INDEX["INSP0"]] is not None else 0
    held_pkg = sum(1 for n in _PKG_MACHINES if held[MACHINE_INDEX[n]] is not None)
    return rec, held_insp0, held_pkg


def _balance(rec, held_insp0, held_pkg):
    """(line_created, rhs) under the topology-A embodiment (docstring)."""
    fs = rec["flow_stats"]
    ss = rec["sbuf_stats"]
    sf = fs["store_final"]
    store_main = sum(
        v
        for k, v in sf.items()
        if k not in _ASM_STORES and k != "SBUF" and k not in _PKG_STORES
    )
    lhs = fs["line_created"]
    rhs = (
        3 * fs["sunk"]
        + store_main
        + fs["kit_A"]
        + fs["kit_B"]
        + fs["kit_C"]
        + (fs["held_line"] - held_pkg - held_insp0)
        + 3 * held_insp0
        + 3 * (fs["held_asm0_batch"] + fs["held_asm12"] + fs["held_rwk0"])
        + 3 * sum(sf[k] for k in _ASM_STORES)
        + fs["xfer_open"]
        + ss["final"]
    )
    return lhs, rhs


@pytest.mark.parametrize("seed", _SEEDS)
def test_conservation_exact_balance_clean(seed):
    rec, held_insp0, held_pkg = _run_with_held(seed, None)
    lhs, rhs = _balance(rec, held_insp0, held_pkg)
    assert lhs == rhs, f"seed={seed} line_created={lhs} rhs={rhs} diff={lhs - rhs}"


def test_conservation_exact_balance_fault():
    rec, held_insp0, held_pkg = _run_with_held(777, _F21_B2)
    lhs, rhs = _balance(rec, held_insp0, held_pkg)
    assert lhs == rhs, f"777 F-21 line_created={lhs} rhs={rhs} diff={lhs - rhs}"
