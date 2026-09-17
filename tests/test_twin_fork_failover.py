"""Todo 3 TDD red: B-pair failover + PKG round-robin + INSP0 late verdict.

Red-first: FAILOVER/PACK_FORK/LATE_VERDICT events and the pkg_rr split do
not exist yet — each test FAILS on the Todo-2 twin (packaged==0, B7S idle,
no INSP0 delay process) and PASSES after Todo 3 lands fork/failover/delay
semantics in src/twin.py. Seed 777, T=300 pins throughout.
"""

import pytest

from src import twin
from src.config import MACHINE_INDEX

pytestmark = pytest.mark.k2

_SEED = 777
_T = 300

_BREAKDOWN_B7P = {
    "id": "F-T3-failover",
    "class": "breakdown",
    "origin": "B7P",
    "t0": 150,
    "dur": 12,
    "mag_sigma": 0.0,
    "extra": {"mttr_mult": 2.0},
}


def test_failover_routes_to_spare_on_DOWN():
    rec = twin.run_episode(_SEED, dict(_BREAKDOWN_B7P))
    fails = [
        e
        for e in rec["events"]
        if e.get("event") == "FAILOVER" and e.get("detail", {}).get("to") == "B7S"
    ]
    assert fails, "breakdown on B7P must reroute B2 output to B7S with FAILOVER"
    assert all(e["detail"]["from"] == "B7P" for e in fails)
    assert all(e["detail"]["reason"] in ("DOWN", "OVERFLOW") for e in fails)
    assert sum(rec["throughput"][MACHINE_INDEX["B7S"]]) > 0


def test_pkg_round_robin_split():
    rec = twin.run_episode(_SEED, None)
    assert rec["flow_stats"]["packaged"] > 0, "C7 fork must feed PKG0 in clean eps"
    forks = [e for e in rec["events"] if e.get("event") == "PACK_FORK"]
    seq = [e["detail"]["to"] for e in forks]
    assert seq, "expected PACK_FORK routing events"
    assert seq[0] == "PKG1", "first part routes to PKG1"
    assert set(seq) == {"PKG1", "PKG2"}, "strict alternation feeds both tails"
    assert all(b != a for a, b in zip(seq, seq[1:])), "no two in a row to one tail"
    sunk = {p["machine"] for p in rec["parts"] if p.get("via") == "PKG"}
    assert sunk == {"PKG1", "PKG2"}


def test_inspect_late_verdict_delays_flag():
    rec = twin.run_episode(_SEED, None)
    verdicts = [e for e in rec["events"] if e.get("event") == "LATE_VERDICT"]
    assert verdicts, "INSP0 must emit LATE_VERDICT per released kit"
    assert all(v["machine"] == "INSP0" for v in verdicts)
    assert all(set(v["detail"]) >= {"part", "verdict"} for v in verdicts)
    assert all(v["detail"]["verdict"] == "DEGRADE" for v in verdicts)


def test_b2_blocked_backpressure_no_loss_when_both_full():
    # Both-pair DOWN/full -> B2 BLOCKED backpressure: with both fork
    # buffers at cap, B2 holds its part BLOCKED (no SBUF divert, no loss).
    # In-episode the 25-cap buffers absorb short DOWN windows, so this is
    # a scripted full-buffer probe of the exact backpressure branch.
    import simpy

    from src.config import BUFFERS, N_MACHINES, T

    noise, _place, drop, _agv, fail = twin._spawn_streams(_SEED)
    shared = {
        "noise": noise,
        "place": _place,
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
        "flow": {"line_created": 0, "packaged": 0},
        "fx": {},
        "gwin": [],
        "qwin": [],
        "pkg_rr": 0,
    }
    env = simpy.Environment()
    up = simpy.Store(env, capacity=BUFFERS["B12"])
    up.items.append({"id": 1, "line": "B", "flag": "OK"})
    pair = simpy.Store(env, capacity=BUFFERS["B2B7P"])
    sib = simpy.Store(env, capacity=BUFFERS["B2B7S"])
    for i in range(BUFFERS["B2B7P"]):
        pair.items.append({"id": 100 + i, "line": "B", "flag": "OK"})
    for i in range(BUFFERS["B2B7S"]):
        sib.items.append({"id": 200 + i, "line": "B", "flag": "OK"})
    sbuf = simpy.Store(env, capacity=30)
    join = simpy.Store(env, capacity=BUFFERS["B7PB8"])
    env.process(
        twin._line_process(
            env,
            {
                "name": "B2",
                "idx": MACHINE_INDEX["B2"],
                "up": up,
                "down": (pair, sib),
                "sbuf": sbuf,
                "stores": {"B7PB8": join},
            },
            shared,
        )
    )
    env.run(until=12)
    b2 = MACHINE_INDEX["B2"]
    assert "BLOCKED" in shared["states"][b2][:12]
    held = shared["held"][b2]
    assert held is not None and held["id"] == 1
    assert not [e for e in shared["events"] if e.get("event") == "DIVERT_SBUF"]
    assert len(pair.items) == BUFFERS["B2B7P"] and len(sib.items) == BUFFERS["B2B7S"]


def test_inspect_hold_three_steps_scripted():
    import simpy

    from src.config import BUFFERS, N_MACHINES, T

    noise, _place, drop, _agv, fail = twin._spawn_streams(_SEED)
    shared = {
        "noise": noise,
        "place": _place,
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
        "qwin": [],
        "pkg_rr": 0,
    }
    env = simpy.Environment()
    up = simpy.Store(env, capacity=BUFFERS["INSP01"])
    down = simpy.Store(env, capacity=BUFFERS["INSP02"])
    up.items.append({"id": 7, "line": "ASM", "flag": "OK", "passes": 0})
    env.process(twin._insp0_process(env, up, down, shared))
    env.run(until=10)
    assert len(down.items) == 1 and down.items[0]["id"] == 7
    assert down.items[0]["flag"] == "DEGRADE"
    verdicts = [e for e in shared["events"] if e.get("event") == "LATE_VERDICT"]
    assert len(verdicts) == 1 and verdicts[0]["detail"]["verdict"] == "DEGRADE"
    tput = shared["tput"][MACHINE_INDEX["INSP0"]]
    first_one = next(t for t in range(10) if tput[t] == 1)
    assert first_one == 3, "intake at t=0 releases exactly 3 steps later"
