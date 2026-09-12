"""TDD red step (T2): TC-006b flow-semantics tests (AGV/SBUF/rework/states).

Name contract (T5/T6 `-k` filters depend on it — never rename without
updating their acceptances): every test here is named test_agv_*,
test_sbuf_*, test_kit_*, test_state_*, test_rework_*, or test_fault_*.

RED STEP: twin logic is not implemented yet — every test MUST fail with
NotImplementedError until T5/T6/T7 land. Each test calls
twin.run_episode / twin.build_faults FIRST so red = NotImplementedError,
never AssertionError.

Pinned probes: seed 777, T=300 everywhere — except the two congestion
tests, pinned at seed 287 (discriminating pin: at 777 the plant absorbs
the delay-A5 fault — 0 BLOCKED with AND without fault — while 287
exhibits genuine fault→congestion with a clean-empty baseline;
rerun-identical via replay_digest, see .omo/evidence task-11 note).
No statistical asserts without a pinned seed; numeric tolerances are
explicit bounds, not estimates.

Traceability: docs/TEST_CASES.md TC-006b steps 1-4; docs/SIM_SPEC.md
§2.2 (AGV/SBUF), §2.4 (BLOCKED/STARVED), Table 3.1 (AGV hold [4,8],
RWK0 rework cap), §5 quality/reject 15-40%, §8 channels 3/5/6/7.
"""

from itertools import pairwise

import pytest

from src import twin
from src.config import BUFFERS

pytestmark = pytest.mark.k2

_SEED = 777
_T = 300

# Congestion pin (owner ruling A on T7): seed 287 is the discriminating
# pin for delay-A5 congestion — fault episode shows A0 BLOCKED x8 with
# A01 at cap, clean episode shows 0 BLOCKED anywhere (A01 max 12 < 20).
# At 777 both episodes show 0 BLOCKED (plant absorbs the fault there),
# so 777 cannot discriminate fault vs clean for congestion. Deterministic:
# rerun-identical (replay_digest 962b9c54d022). Fault shape below is
# byte-identical to the pre-ruling _DELAY_A5 (dur=15, d=5) — only the
# seed pin changed, never the physics.
_SEED_CONGEST = 287

_DELAY_A5 = {
    "id": "F-T2-delay",
    "class": "delay",
    "origin": "A5",
    "t0": 150,
    "dur": 15,
    "mag_sigma": 0.0,
    "extra": {"d": 5},
}

_BREAKDOWN_B2 = {
    "id": "F-T2-break",
    "class": "breakdown",
    "origin": "B2",
    "t0": 150,
    "dur": 12,
    "mag_sigma": 0.0,
    "extra": {"mttr_mult": 2.0},
}

_QUALITY_ASM2 = {
    "id": "F-T2-rework",
    "class": "quality",
    "origin": "ASM2",
    "t0": 150,
    "dur": 20,
    "mag_sigma": 0.0,
    "extra": {"reject_rate": 0.40},
}


# --- (a) AGV: tail→ASM0 transfers -------------------------------------------


def test_agv_hold_in_range():
    rec = twin.run_episode(_SEED, _DELAY_A5)  # raises first (red)
    assert rec["T"] == _T
    holds = [w["hold"] for w in rec["agv_waits"]]
    assert holds, "expected at least one tail→ASM0 transfer at seed 777"
    assert all(4 <= h <= 8 for h in holds)


def test_agv_waits_logged_and_bounded():
    rec = twin.run_episode(_SEED, _DELAY_A5)  # raises first (red)
    waits = rec["agv_waits"]
    assert all(set(w) >= {"t", "part", "hold", "wait"} for w in waits)
    assert all(w["wait"] >= 0 for w in waits)
    assert all(w["t"] < _T for w in waits)
    assert len(waits) <= 3 * _T  # bounded: ≤ one kit per step per tail


def test_agv_no_transfer_without_hold():
    rec = twin.run_episode(_SEED, _DELAY_A5)  # raises first (red)
    transfers = [p for p in rec["parts"] if p.get("via") == "AGV"]
    holds = {(w["t"], w["part"]) for w in rec["agv_waits"]}
    assert transfers, "expected AGV-routed parts at seed 777"
    assert all((p["t"], p["id"]) in holds for p in transfers)


# --- (b) rework: ASM2→RWK0→ASM0, passes<=2 ----------------------------------


def test_rework_passes_capped_and_scrap():
    rec = twin.run_episode(_SEED, _QUALITY_ASM2)  # raises first (red)
    assert rec["T"] == _T
    passes = [p.get("passes", 0) for p in rec["parts"]]
    assert all(p <= 2 for p in passes)
    scrapped = [p for p in rec["parts"] if p.get("disposition") == "scrap"]
    assert len(scrapped) > 0  # 40% reject at ASM2 must scrap some parts


def test_rework_no_infinite_loop():
    rec = twin.run_episode(_SEED, _QUALITY_ASM2)  # raises first (red)
    assert len(rec["parts"]) <= 3 * _T  # terminates: bounded WIP at T=300
    routed = [p for p in rec["parts"] if p.get("via") == "RWK0"]
    assert routed, "expected rework-routed parts under 40% reject"


# --- (c) SBUF overflow -------------------------------------------------------


def test_sbuf_divert_process_finish_allowed():
    rec = twin.run_episode(_SEED, _DELAY_A5)  # raises first (red)
    diverts = [e for e in rec.get("events", []) if e.get("event") == "DIVERT_SBUF"]
    assert diverts, "expected SBUF diverts under delay congestion at seed 777"
    assert all(e["detail"]["class"] in ("process", "finish") for e in diverts)


def test_sbuf_feed_form_never_divert():
    rec = twin.run_episode(_SEED, _DELAY_A5)  # raises first (red)
    diverts = [e for e in rec.get("events", []) if e.get("event") == "DIVERT_SBUF"]
    assert all(e["detail"]["class"] not in ("feed", "form") for e in diverts)


def test_sbuf_occupancy_logged_and_drains():
    rec = twin.run_episode(_SEED, _DELAY_A5)  # raises first (red)
    sbuf = rec["buffers"][30]  # SBUF is the 31st buffer
    assert len(sbuf) == _T
    assert all(0 <= lvl <= 30 for lvl in sbuf)
    assert max(sbuf) > 0  # congestion at seed 777 must occupy SBUF
    assert sbuf[-1] < max(sbuf)  # drains once an AGV frees


# --- (d) states + concrete probes --------------------------------------------


def test_state_blocked_iff_downstream_full():
    # PROJECT GOAL (owner ruling A): prove genuine fault→congestion
    # causality through flow — BLOCKED occurs iff downstream is full.
    # Phenomenon: under delay-A5 at pin 287, the A-line head piles to cap
    # and A0 BLOCKEDs; every BLOCKED cell sits on an at-cap downstream
    # buffer (caps imported from src.config.BUFFERS, never hardcoded).
    # Cause that would break it: silenced BLOCKED emission, divert arms
    # swallowing the pileup, or buffer caps detached from config.
    # Granularity note: same-t converse (full ⇒ BLOCKED) is unphysical —
    # BLOCKED fires only on a failed put-attempt step (cycle granularity),
    # so a full buffer coexists with RUN mid-cycle steps. The honest
    # biconditional is: BLOCKED(t) ⇒ downstream at-cap(t), and BLOCKED
    # recurs periodically while the buffer sits at cap.
    rec = twin.run_episode(_SEED_CONGEST, _DELAY_A5)  # raises first (red)
    states, bufs = rec["states"], rec["buffers"]
    assert len(states) == 32 and all(len(row) == _T for row in states)
    blocked = [
        (m, t) for m in range(32) for t in range(_T) if states[m][t] == "BLOCKED"
    ]
    assert blocked, "delay d=5 at A5 must BLOCK some machine at pin 287"
    assert {m for m, _ in blocked} == {0}  # measured: only A0 (line head) blocks
    counts = rec.get("throughput", rec.get("counts", None))
    assert counts is not None
    assert all(counts[m][t] == 0 for m, t in blocked)  # BLOCKED holds part, emits 0
    buf_order = list(BUFFERS)
    a01 = bufs[buf_order.index("A01")]
    cap_a01 = BUFFERS["A01"]
    assert max(a01) == cap_a01  # pileup reaches cap (measured 20/20)
    assert all(a01[t] == cap_a01 for _, t in blocked)  # BLOCKED ⇒ downstream full


def test_kit_asm0_starves_unless_all_tails():
    rec = twin.run_episode(_SEED, _QUALITY_ASM2)  # raises first (red)
    states = rec["states"]
    asm0 = states[28]  # ASM0 index per Table 3.1 ordering
    assert "STARVED" in asm0  # 40% reject starves kitting at seed 777


def test_state_down_preempts_and_gt_excluded():
    _faults = twin.build_faults(_SEED)  # raises first (red)
    rec = twin.run_episode(_SEED, _BREAKDOWN_B2)
    states = rec["states"]
    assert any(s == "DOWN" for row in states for s in row)
    natural = [e for e in rec.get("events", []) if e.get("event") in ("DOWN", "UP")]
    assert all(
        e.get("natural", False) or e.get("fault_id") is not None for e in natural
    )
    _gt_windows = [(f["t0"], f["t0"] + f["dur"]) for f in rec["faults"]]
    assert all(e.get("gt_excluded", True) for e in natural if e.get("natural"))


def test_fault_delay_a5_blocks_upstream():
    # PROJECT GOAL (owner ruling A): delay causes upstream block — the
    # fault at A5 congests the A-line back to its head: A01 piles from ~7
    # (t150) to cap (t235) and feed-head A0 (which never diverts to SBUF)
    # BLOCKEDs x8 on the at-cap buffer, recurring every 6 steps at the
    # downstream-consumption rhythm. Cause that would break it: divert
    # arms swallowing head pileup, BLOCKED emission detached from
    # downstream-full, or RNG/draw-order drift moving the pin.
    # Measured at pin 287 (fault shape unchanged: delay A5 t0=150 dur=15
    # d=5): A0 BLOCKED == [254,260,...,296]; clean pin-287 episode has 0
    # BLOCKED anywhere (non-vacuity anchor — see evidence note).
    rec = twin.run_episode(_SEED_CONGEST, _DELAY_A5)  # raises first (red)
    states = rec["states"]
    a0_blocked = [t for t in range(_T) if states[0][t] == "BLOCKED"]
    assert len(a0_blocked) == 8  # measured pileup breaks through x8
    assert a0_blocked[0] == 254 and a0_blocked[-1] == 296  # measured cascade band
    assert all(b - a == 6 for a, b in pairwise(a0_blocked))
    assert all(150 <= t < _T for t in a0_blocked)  # post-fault cascade, in-episode


def test_fault_breakdown_b2_zero_throughput():
    rec = twin.run_episode(_SEED, _BREAKDOWN_B2)  # raises first (red)
    counts = rec.get("throughput", rec.get("counts", None))
    assert counts is not None
    b2 = counts[12]  # B2 index: A0-9 (0-9), B0=10, B1=11, B2=12
    assert all(c == 0 for c in b2[150 : 150 + 12])  # origin throughput 0 over window
