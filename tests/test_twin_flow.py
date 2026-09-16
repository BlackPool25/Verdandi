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
the delay-A2 fault into the C7 tail while 287 exhibits genuine
fault→tail-saturation with a clean-empty baseline; rerun-identical via
replay_digest, see .omo/evidence task-11 note).
No statistical asserts without a pinned seed; numeric tolerances are
explicit bounds, not estimates.

Traceability: docs/TEST_CASES.md TC-006b steps 1-4; docs/SIM_SPEC.md
§2.2 (AGV/SBUF), §2.4 (BLOCKED/STARVED), Table 3.1 (AGV hold [4,8],
RWK0 rework cap), §5 quality/reject 15-40%, §8 channels 3/5/6/7.
"""

import pytest

from src import twin
from src.config import BUFFERS

pytestmark = pytest.mark.k2

_SEED = 777
_T = 300

# Congestion pin (topology-A: short lines absorb mid-line delay — the A27
# gap never piles, so the pin moved from delay-A5 to delay-A2, whose
# backpressure concentrates at the AGV-drained C7 tail; clean-287 episode
# has 0 BLOCKED anywhere — non-vacuity anchor).
_SEED_CONGEST = 287

_DELAY_A2 = {
    "id": "F-T2-delay",
    "class": "delay",
    "origin": "A2",
    "t0": 150,
    "dur": 15,
    "mag_sigma": 0.0,
    "extra": {"d": 5},
}

# Strong delay pin for tail-saturation: d=6 dur=25 on A2 at pin 287 piles
# the C7 tail stage to cap (C7 BLOCKED x18, contiguous [275,292]).
_DELAY_A2_TAIL = {
    "id": "F-T2-delay-tail",
    "class": "delay",
    "origin": "A2",
    "t0": 150,
    "dur": 25,
    "mag_sigma": 0.0,
    "extra": {"d": 6},
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
    rec = twin.run_episode(_SEED, _DELAY_A2)  # raises first (red)
    assert rec["T"] == _T
    holds = [w["hold"] for w in rec["agv_waits"]]
    assert holds, "expected at least one tail→ASM0 transfer at seed 777"
    assert all(4 <= h <= 8 for h in holds)


def test_agv_waits_logged_and_bounded():
    rec = twin.run_episode(_SEED, _DELAY_A2)  # raises first (red)
    waits = rec["agv_waits"]
    assert all(set(w) >= {"t", "part", "hold", "wait"} for w in waits)
    assert all(w["wait"] >= 0 for w in waits)
    # Owner-approved option C re-pin (was: all w["t"] < _T): the
    # land-grace drain phase lands in-flight xfers in [T, T+GRACE], so
    # landings carry t up to _T + AGV_DRAIN_GRACE. xfer_open == 0 (the
    # drainage proof) is asserted by tests/test_twin_duty.py.
    from src.config import AGV_DRAIN_GRACE

    assert all(w["t"] <= _T + AGV_DRAIN_GRACE for w in waits)
    assert len(waits) <= 3 * _T  # bounded: ≤ one kit per step per tail


def test_agv_no_transfer_without_hold():
    rec = twin.run_episode(_SEED, _DELAY_A2)  # raises first (red)
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
    rec = twin.run_episode(_SEED, _DELAY_A2)  # raises first (red)
    diverts = [e for e in rec.get("events", []) if e.get("event") == "DIVERT_SBUF"]
    assert diverts, "expected SBUF diverts under delay congestion at seed 777"
    assert all(e["detail"]["class"] in ("process", "finish") for e in diverts)


def test_sbuf_feed_form_never_divert():
    rec = twin.run_episode(_SEED, _DELAY_A2)  # raises first (red)
    diverts = [e for e in rec.get("events", []) if e.get("event") == "DIVERT_SBUF"]
    assert all(e["detail"]["class"] not in ("feed", "form") for e in diverts)


def test_sbuf_occupancy_logged_and_drains():
    rec = twin.run_episode(_SEED, _DELAY_A2)  # raises first (red)
    buf_order = list(BUFFERS)
    sbuf = rec["buffers"][buf_order.index("SBUF")]  # SBUF row by roster order
    assert len(sbuf) == _T
    assert all(0 <= lvl <= 30 for lvl in sbuf)
    # Owner-approved option C re-pin (was: max(sbuf) > 0 and
    # sbuf[-1] < max(sbuf)): AGV 2->3 drains SBUF within-step, so the
    # per-step monitor never samples occupancy (row all zeros) even
    # though DIVERT_SBUF events still fire (see
    # test_sbuf_divert_process_finish_allowed). Pin the drain instead:
    # SBUF ends empty.
    assert sbuf[-1] == 0  # SBUF drains by T (AGV cap 3 keeps up)


# --- (d) states + concrete probes --------------------------------------------


def test_state_blocked_iff_downstream_full():
    # PROJECT GOAL: prove genuine fault→congestion causality through flow
    # — BLOCKED occurs iff downstream is full.
    # Owner-approved option C re-pin (was: strong delay-A2 at pin 287
    # BLOCKs only C7 x14 [285,298] with _C7TAIL final at cap 15): TAKT5
    # takt-matching + AGV 2->3 eliminated tail saturation by design —
    # buffers run empty so no fault within range can fill a cap-15
    # buffer (needs ~75 steps at takt 5 vs max dur 40). The pin is now
    # absorption: the strongest fault leaves zero BLOCKED anywhere AND
    # no buffer at cap (both sides of the iff hold). Plant BLOCKED share
    # 0.000 on all 5 clean duty seeds corroborates. If a future retime
    # reintroduces saturation, this pin (and the pile-up bound) trips.
    from src.config import MACHINE_INDEX, MACHINES

    rec = twin.run_episode(_SEED_CONGEST, _DELAY_A2_TAIL)  # raises first (red)
    states = rec["states"]
    assert len(states) == 26 and all(len(row) == _T for row in states)
    c7 = MACHINE_INDEX["C7"]
    blocked = [
        (m, t) for m in range(26) for t in range(_T) if states[m][t] == "BLOCKED"
    ]
    assert blocked == []  # TAKT5 absorbs the strongest delay fault: no BLOCKED
    assert c7 not in {m for m, _ in blocked}  # C7 tail stage stays clear
    store_final = rec["flow_stats"]["store_final"]
    assert store_final["_C7TAIL"] < MACHINES["C7"]["buffer_cap"] == 15
    clean = twin.run_episode(_SEED_CONGEST, None)
    assert not any(
        s == "BLOCKED" for row in clean["states"] for s in row
    )  # non-vacuity anchor


def test_kit_asm0_starves_unless_all_tails():
    rec = twin.run_episode(_SEED, _QUALITY_ASM2)  # raises first (red)
    states = rec["states"]
    from src.config import MACHINE_INDEX

    asm0 = states[MACHINE_INDEX["ASM0"]]  # ASM0 index per MACHINE_INDEX ordering
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


def test_fault_delay_a2_backpressures_c7_tail():
    # PROJECT GOAL: delay causes downstream tail saturation — the strong
    # delay-A2 fault congests the AGV-drained C7 tail to cap: C7 BLOCKEDs
    # x14 as one contiguous late run [285,298] while no mid-line machine
    # ever blocks (short lines absorb). Cause that would break it: AGV
    # drain detached from the tail, BLOCKED emission detached from
    # downstream-full, or RNG/draw-order drift moving the pin.
    # Measured at pin 287 (fault shape: delay A2 t0=150 dur=40 d=6,
    # natural breakdown off to isolate the fault-driven cascade;
    # re-pinned in Todo 3: INSP0's normative 3-step hold replaced the
    # Todo-2 serial placeholder and the shared fail-stream lottery
    # redistributed natural DOWNs, moving the old x18 [275,292] pin —
    # streams/slots/coefficients untouched, trajectories re-based).
    # Owner-approved option C re-pin (was: C7 BLOCKED x14 contiguous
    # [285,298]; Todo-3 pin x18 [275,292] before that): TAKT5 (C7 3->5 +
    # AGV 2->3) drains the tail faster than the fault piles it — _C7TAIL
    # final 1 vs cap 15, zero BLOCKED even at dur=40/BD-off. The
    # backpressure phenomenon is absorbed by design, not by detector
    # tuning; the pin now guards the absorption (any regression
    # re-saturates the tail and trips len != 0).
    # Deterministic: 2x rerun identical via replay_digest (see evidence).
    from src.config import MACHINE_INDEX

    _FAULT = dict(_DELAY_A2_TAIL)
    _FAULT["dur"] = 40
    rec = twin.run_episode(
        _SEED_CONGEST, _FAULT, enable_natural_breakdown=False
    )  # raises first (red)
    states = rec["states"]
    c7_blocked = [t for t in range(_T) if states[MACHINE_INDEX["C7"]][t] == "BLOCKED"]
    assert c7_blocked == []  # TAKT5 absorbs: no tail pileup breakthrough
    assert rec["flow_stats"]["store_final"]["_C7TAIL"] < 15  # tail drains


def test_rework_asm0_kit_preserves_reject_and_passes():
    # ASM0 kitting rebuild must preserve passes/REJECT (Copilot :739,
    # blocks T-A8): a REJECT-flagged rework part re-entering via kit C
    # keeps its flag and max passes in the rebuilt kit (no passes:0 reset).
    import simpy

    from src.config import BUFFERS, N_MACHINES, T

    noise, _place, drop, _agv, fail = twin._spawn_streams(_SEED)
    shared = {
        "noise": noise,
        "drop": drop,
        "fail": fail,
        "enable_bd": False,
        "obs": [[0.0] * T for _ in range(N_MACHINES)],
        "states": [["RUN"] * T for _ in range(N_MACHINES)],
        "tput": [[0] * T for _ in range(N_MACHINES)],
        "events": [],
        "pid": [1000],
        "held": [None] * N_MACHINES,
        "flow": {"asm_created": 0},
        "fx": {},
        "gwin": [],
        "qwin": [],
    }
    kit = {
        "A": [{"id": 1, "line": "A", "flag": "OK", "passes": 0}],
        "B": [{"id": 2, "line": "B", "flag": "OK", "passes": 0}],
        "C": [{"id": 3, "line": "C", "flag": "REJECT", "passes": 1}],
    }
    env = simpy.Environment()
    asm01 = simpy.Store(env, capacity=BUFFERS["ASM01"])
    env.process(twin._asm0_process(env, asm01, kit, shared))
    env.run(until=20)
    assert len(asm01.items) == 1
    built = asm01.items[0]
    assert built["flag"] == "REJECT"
    assert built["passes"] == 1


def test_fault_breakdown_mttr_mult_scales_down():
    # mttr_mult scales the injected DOWN window (Copilot :303): same
    # origin/dur, mult=3 must hold origin DOWN longer than mult=1.
    # Deterministic: seed 777, natural breakdown off (isolates injected).
    from src.config import MACHINE_INDEX

    def _mk(mult):
        return {
            "id": "F-T2-mttr",
            "class": "breakdown",
            "origin": "B2",
            "t0": 150,
            "dur": 12,
            "mag_sigma": 0.0,
            "extra": {"mttr_mult": mult},
        }

    r1 = twin.run_episode(_SEED, _mk(1.0), enable_natural_breakdown=False)
    r3 = twin.run_episode(_SEED, _mk(3.0), enable_natural_breakdown=False)
    b2 = MACHINE_INDEX["B2"]
    n1 = sum(1 for s in r1["states"][b2] if s == "DOWN")
    n3 = sum(1 for s in r3["states"][b2] if s == "DOWN")
    assert n3 > n1, f"mttr_mult=3 must extend DOWN: {n3} <= {n1}"
    assert n1 == 12  # mult=1 keeps the exact window


def test_fault_breakdown_b2_zero_throughput():
    rec = twin.run_episode(_SEED, _BREAKDOWN_B2)  # raises first (red)
    counts = rec.get("throughput", rec.get("counts", None))
    assert counts is not None
    from src.config import MACHINE_INDEX

    b2 = counts[MACHINE_INDEX["B2"]]  # B2 index per MACHINE_INDEX ordering
    assert all(c == 0 for c in b2[150 : 150 + 12])  # origin throughput 0 over window


_QUALITY_B2 = {
    "id": "F-T2-quality-scope",
    "class": "quality",
    "origin": "B2",
    "t0": 150,
    "dur": 20,
    "mag_sigma": 0.0,
    "extra": {"reject_rate": 0.40},
}


def test_rework_quality_scoped_to_origin():
    # Quality reject windows are origin-scoped: a 40% quality fault at B2
    # must NOT raise the ASM2 reject rate (zero rejects, zero scraps, no
    # RWK0 rework — same as a clean episode). Pinned at seed 777 with the
    # default breakdown stream: the unscoped window leaks one reject here.
    rec = twin.run_episode(_SEED, _QUALITY_B2)
    assert rec["flow_stats"]["rejected"] == 0
    assert rec["flow_stats"]["scrapped"] == 0
    assert not [p for p in rec["parts"] if p.get("via") == "RWK0"]


def test_rework_asm2_holds_reject_when_rwk_full():
    # ASM2 full-buffer hold (Wave-1 T-A8, depends on T-A7): a REJECT part
    # facing a full RWK_RET holds ASM2 BLOCKED with flag/passes preserved
    # (no re-roll to OK on the next step); freeing a slot enqueues it.
    # Deterministic: scripted place draws (reject once, then accept-bait),
    # natural breakdown off, RWK_RET pre-filled to cap.
    import simpy

    from src.config import BUFFERS, MACHINE_INDEX, N_MACHINES, T

    noise, _place, drop, _agv, fail = twin._spawn_streams(_SEED)
    draws = iter([0.1] + [0.9] * 64)

    class _ScriptedPlace:
        def random(self):
            return next(draws)

    asm2_idx = MACHINE_INDEX["ASM2"]
    shared = {
        "noise": noise,
        "place": _ScriptedPlace(),
        "drop": drop,
        "fail": fail,
        "enable_bd": False,
        "obs": [[0.0] * T for _ in range(N_MACHINES)],
        "states": [["RUN"] * T for _ in range(N_MACHINES)],
        "tput": [[0] * T for _ in range(N_MACHINES)],
        "events": [],
        "parts": [],
        "pid": [1000],
        "held": [None] * N_MACHINES,
        "flow": {"sunk": 0, "scrapped": 0, "rejected": 0},
        "fx": {},
        "gwin": [],
        "qwin": [(0, T, 0.4, "ASM2")],
    }
    env = simpy.Environment()
    up = simpy.Store(env, capacity=BUFFERS["INSP02"])
    rwk = simpy.Store(env, capacity=BUFFERS["RWK_RET"])
    for i in range(BUFFERS["RWK_RET"]):
        rwk.items.append({"id": 900 + i, "line": "ASM", "flag": "REJECT", "passes": 1})
    up.items.append({"id": 7, "line": "ASM", "flag": "OK", "passes": 0})
    shared["rwk_ret"] = rwk
    env.process(twin._asm_mid_process(env, "ASM2", up, None, shared))
    env.run(until=6)
    assert "BLOCKED" in shared["states"][asm2_idx][:6]
    held = shared["held"][asm2_idx]
    assert held is not None and held["id"] == 7
    assert held["flag"] == "REJECT"  # no re-roll to OK while held
    assert held.get("passes", 0) == 0
    assert shared["flow"]["sunk"] == 0
    assert shared["flow"]["rejected"] == 0
    rwk.items.pop(0)  # free one slot: held part must enqueue, not re-roll
    env.run(until=12)
    assert shared["flow"]["rejected"] == 1
    assert shared["held"][asm2_idx] is None
    assert held["passes"] == 1 and held["flag"] == "REJECT"
    assert any(p["id"] == 7 for p in rwk.items)
