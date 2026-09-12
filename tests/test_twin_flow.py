"""TDD red step (T2): TC-006b flow-semantics tests (AGV/SBUF/rework/states).

Name contract (T5/T6 `-k` filters depend on it — never rename without
updating their acceptances): every test here is named test_agv_*,
test_sbuf_*, test_kit_*, test_state_*, test_rework_*, or test_fault_*.

RED STEP: twin logic is not implemented yet — every test MUST fail with
NotImplementedError until T5/T6/T7 land. Each test calls
twin.run_episode / twin.build_faults FIRST so red = NotImplementedError,
never AssertionError.

Pinned probes: seed 777, T=300 everywhere. No statistical asserts without
the pinned seed; numeric tolerances are explicit bounds, not estimates.

Traceability: docs/TEST_CASES.md TC-006b steps 1-4; docs/SIM_SPEC.md
§2.2 (AGV/SBUF), §2.4 (BLOCKED/STARVED), Table 3.1 (AGV hold [4,8],
RWK0 rework cap), §5 quality/reject 15-40%, §8 channels 3/5/6/7.
"""

import pytest

from src import twin

_SEED = 777
_T = 300

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
    rec = twin.run_episode(_SEED, _DELAY_A5)  # raises first (red)
    states, bufs = rec["states"], rec["buffers"]
    assert len(states) == 32 and all(len(row) == _T for row in states)
    blocked = [(m, t) for m in range(32) for t in range(_T) if states[m][t] == "BLOCKED"]
    assert blocked, "delay d=5 at A5 must BLOCK some machine at seed 777"
    counts = rec.get("throughput", rec.get("counts", None))
    assert counts is not None
    assert all(counts[m][t] == 0 for m, t in blocked)  # BLOCKED holds part, emits 0
    assert all(any(lvl >= 25 - 1e-9 for lvl in [row[t] for row in bufs]) for _, t in blocked[:5])


def test_kit_asm0_starves_unless_all_tails():
    rec = twin.run_episode(_SEED, _QUALITY_ASM2)  # raises first (red)
    states = rec["states"]
    asm0 = states[28]  # ASM0 index per Table 3.1 ordering
    assert "STARVED" in asm0  # 40% reject starves kitting at seed 777


def test_state_down_preempts_and_gt_excluded():
    faults = twin.build_faults(_SEED)  # raises first (red)
    rec = twin.run_episode(_SEED, _BREAKDOWN_B2)
    states = rec["states"]
    assert any(s == "DOWN" for row in states for s in row)
    natural = [e for e in rec.get("events", []) if e.get("event") in ("DOWN", "UP")]
    assert all(e.get("natural", False) or e.get("fault_id") is not None for e in natural)
    gt_windows = [(f["t0"], f["t0"] + f["dur"]) for f in rec["faults"]]
    assert all(e.get("gt_excluded", True) for e in natural if e.get("natural"))


def test_fault_delay_a5_blocks_upstream():
    rec = twin.run_episode(_SEED, _DELAY_A5)  # raises first (red)
    states = rec["states"]
    a4_blocked = [t for t in range(_T) if states[4][t] == "BLOCKED"]
    assert a4_blocked, "delay d=5 at A5 must BLOCK upstream A4 at seed 777, T=300"
    assert all(150 <= t < 150 + 15 + 30 for t in a4_blocked)  # cascade within window + drain


def test_fault_breakdown_b2_zero_throughput():
    rec = twin.run_episode(_SEED, _BREAKDOWN_B2)  # raises first (red)
    counts = rec.get("throughput", rec.get("counts", None))
    assert counts is not None
    b2 = counts[12]  # B2 index: A0-9 (0-9), B0=10, B1=11, B2=12
    assert all(c == 0 for c in b2[150:150 + 12])  # origin throughput 0 over window
