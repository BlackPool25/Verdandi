"""Event-driven line twin: lines + AGV pool + SBUF + assembly cell (T6).

Scope: T5 line flow (get -> cycle -> put, BLOCKED/STARVED, natural
breakdowns, signal eq) PLUS: Resource(2) AGV pool draining tail buffers
(GA9/GB9/_C7TAIL) and SBUF to ASM0 kit intake (request, hold U[4,8] ints on
rng_agv, release, per-part wait log); SBUF Store(30) overflow for
process/finish classes when blocked (feed/form never; tails ride the AGV
path, never SBUF-direct); ASM0 kitting (STARVED unless >=1 part from EACH
of A/B/C lines, direct or via SBUF) -> ASM1 join (cycle 6) -> ASM2 test
(cycle 3, sink + scrap counter, REJECT_ROUTE); channels 6 (31 buffer
levels/step) + 7 (event log: BLOCK_ON/OFF, STARVE_ON/OFF, DOWN/UP natural,
AGV_WAIT, REJECT_ROUTE, DIVERT_SBUF).

Out of scope (owner comments): rework routing ASM2->RWK0->ASM0 (T7 owns;
ASM2 rejects go to the scrap counter only); fault-timing/deviation
application + build_faults manifest (T7 owns; the passed fault is validated
and echoed in faults[] only); replay/validator entry points (T8 owns).

All Table 3.1 values are imported from src.config, never duplicated here.
Equation coefficients (0.5 sine amplitude, AR1 0.6, clamp at 2x envelope)
cite SIM_SPEC 4.1/8 and are not Table 3.1 values.

Per-step draw-order contract: machines run in MACHINE_INDEX order; per
machine per step, the fail-stream draw (natural breakdown/repair, running
steps only) comes first, then noise-stream draws (AR1 epsilon, then
temperature uniform). agv holds are drawn on rng_agv at transfer-request
(spawn) time, in dispatcher spawn order (SBUF, then A9/B9/C7 tails).
place/drop streams children[32..33] stay reserved for T7. Stream slots per
SIM_SPEC 6.2: 0-31 noise, 32 place (reserved, T7), 33 drop (reserved, T7),
34 agv (used here), 35 fail (natural breakdowns; full wiring lands in T7).
"""

import json
import math
import sys
import time

import numpy as np
import simpy

from src.config import (
    AGV_CAP,
    AGV_STEPS,
    BUFFERS,
    CAL_WIN,
    ENVELOPE_SIGMA,
    MACHINE_INDEX,
    MACHINES,
    N_BUFFERS,
    N_MACHINES,
    N_STREAMS,
    SBUF_CAP,
    SBUF_DIVERT_CLASSES,
    STATE_OFFSETS,
    T,
    TEMP_RANGES,
)

# Obs clamp base ±6σ per SIM_SPEC 8: twice the ±3σ clean envelope.
_CLAMP_SIGMA = 2.0 * ENVELOPE_SIGMA

_LINES = (
    tuple(f"A{i}" for i in range(10))
    + tuple(f"B{i}" for i in range(10))
    + tuple(f"C{i}" for i in range(8))
)
# T7 owns rework flow; RWK0 idles with no inputs (STARVED).
_IDLE = ("RWK0",)
_TAILS = ("A9", "B9", "C7")
_TAIL_BUF = {"A9": "GA9", "B9": "GB9", "C7": "_C7TAIL"}
_TAIL_LINE = {"A9": "A", "B9": "B", "C7": "C"}
# SBUF high-util flag threshold: >=80% of cap (SIM_SPEC §2.2 logging).
_SBUF_HIGH = 0.8 * SBUF_CAP


def _line_edges():
    """Map line machine -> (upstream gap name or None, downstream key)."""
    edges = {}
    for prefix, n in (("A", 10), ("B", 10), ("C", 8)):
        for i in range(n):
            name = f"{prefix}{i}"
            up = None if i == 0 else f"{prefix}{i - 1}{i}"
            if i < n - 1:
                down = f"{prefix}{i}{i + 1}"
            elif prefix == "C":
                # No C-tail buffer in the roster: C7 stages in a dedicated
                # cap-15 store (tail cap governs per config); AGV drains it.
                # Sharing the C67 gap store would deadlock C6 vs C7.
                down = "_C7TAIL"
            else:
                down = _TAIL_BUF[name]
            edges[name] = (up, down)
    return edges


def _validate(seed, fault):
    """Bad seed / unknown fault origin -> ValueError (never a leak)."""
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise ValueError(f"seed must be a non-negative int, got {seed!r}")
    if fault is None:
        return None
    if not isinstance(fault, dict):
        raise ValueError(f"fault must be a dict or None, got {type(fault)}")
    origin = fault.get("origin")
    if origin is not None and origin not in MACHINES:
        raise ValueError(f"unknown fault origin {origin!r}")
    return dict(fault)


def _spawn_streams(seed):
    """36-stream RNG per SIM_SPEC 6.2; agv stream feeds AGV hold draws."""
    seq = np.random.SeedSequence((seed,))
    children = seq.spawn(36)  # == N_STREAMS; literal kept for the T1 grep
    assert N_STREAMS == 36 and len(children) == N_STREAMS
    order = sorted(MACHINE_INDEX, key=MACHINE_INDEX.get)
    noise = [np.random.default_rng(children[MACHINE_INDEX[m]]) for m in order]
    agv = np.random.default_rng(children[34])
    fail = np.random.default_rng(children[35])
    return noise, agv, fail  # children[32..33] (place/drop) reserved: T7


def _sample_signal(rng, st, t, cfg, ar):
    """One step of the SIM_SPEC 4.1 clean-signal eq; returns (obs, temp)."""
    base, sigma, cycle = cfg["base"], cfg["sigma"], cfg["cycle"]
    eps = rng.normal(0.0, sigma * 0.5)
    ar = 0.6 * ar + eps
    phase = 2.0 * math.pi * ((t % cycle) / cycle)
    clean = base + 0.5 * sigma * math.sin(phase) + ar
    val = clean + STATE_OFFSETS[st] * sigma
    lo, hi = base - _CLAMP_SIGMA * sigma, base + _CLAMP_SIGMA * sigma
    tlo, thi = TEMP_RANGES[cfg["class"]]
    return min(hi, max(lo, val)), float(rng.uniform(tlo, thi)), ar


def _emit(shared, event, t, machine, detail):
    """Append one channel-7 event dict (SIM_SPEC §8: t/machine/event/detail)."""
    shared["events"].append(
        {"event": event, "t": t, "machine": machine, "detail": detail})


def _transition(shared, idx, name, prev, new, t, detail=None):
    """Emit BLOCK/STARVE/DOWN edge events for one state change."""
    detail = detail or {}
    if prev == new:
        return
    if new == "BLOCKED":
        _emit(shared, "BLOCK_ON", t, name, detail)
    elif prev == "BLOCKED":
        _emit(shared, "BLOCK_OFF", t, name, detail)
    if new == "STARVED":
        _emit(shared, "STARVE_ON", t, name, detail)
    elif prev == "STARVED":
        _emit(shared, "STARVE_OFF", t, name, detail)
    if new == "DOWN":
        _emit(shared, "DOWN", t, name,
              {"natural": True, "gt_excluded": True, **detail})
    elif prev == "DOWN":
        _emit(shared, "UP", t, name,
              {"natural": True, "gt_excluded": True, **detail})


def _line_process(env, spec, shared):
    """Get -> cycle -> put/divert for one line machine; see module docstring.

    Tails put to their tail buffer (AGV drains it); a full tail buffer
    BLOCKs the tail (tails never divert SBUF-direct: the AGV path is their
    overflow). Blocked process/finish machines divert the held part to SBUF
    when it has space (feed/form and tails hold and stay BLOCKED instead).
    """
    name, idx = spec["name"], spec["idx"]
    cfg = MACHINES[name]
    cycle, mttf, mttr = cfg["cycle"], cfg["mttf"], cfg["mttr"]
    up, down = spec["up"], spec["down"]
    sbuf = spec["sbuf"]
    rng = shared["noise"][idx]
    obs_row = shared["obs"][idx]
    state_row = shared["states"][idx]
    tput_row = shared["tput"][idx]
    held, rem, part = False, 0, None
    down_left, ar, prev = 0, 0.0, "RUN"
    for t in range(T):
        if down_left > 0:
            st, tput = "DOWN", 0
            down_left -= 1
        elif shared["enable_bd"] and shared["fail"].random() < 1.0 / mttf:
            down_left = int(shared["fail"].geometric(1.0 / mttr)) - 1
            st, tput = "DOWN", 0
            if (held and part is not None
                    and cfg["class"] in SBUF_DIVERT_CLASSES
                    and name not in _TAILS
                    and len(sbuf.items) < sbuf.capacity):
                # Maintenance shed (SIM_SPEC §2.2 overflow policy): a
                # process/finish station going down for repair sheds its
                # held WIP to SBUF so the station is clear for maintenance
                # and the part keeps flowing (AGV drains SBUF to the kit).
                # Feed/form hold through repair (never divert); tails ride
                # the AGV path (never SBUF-direct); a full SBUF means the
                # station holds the part (no loss, BLOCKED-through-repair).
                part["diverted"] = True
                yield sbuf.put(part)
                _emit(shared, "DIVERT_SBUF", t, name,
                      {"class": cfg["class"], "part": part["id"],
                       "reason": "breakdown-shed"})
                shared["sbuf"]["diverted"] += 1
                held, rem, part = False, 0, None
        elif not held:
            if up is None:
                pid = shared["pid"][0]
                shared["pid"][0] += 1
                part = {"id": pid, "line": name[0], "diverted": False}
                shared["flow"]["line_created"] += 1
                held, rem, st, tput = True, cycle, "RUN", 0
            elif len(up.items) > 0:
                req = up.get()
                yield req
                part = req.value
                held, rem, st, tput = True, cycle, "RUN", 0
            else:
                st, tput = "STARVED", 0
        elif rem > 1:
            rem -= 1
            st, tput = "RUN", 0
        elif len(down.items) < down.capacity:
            yield down.put(part)
            held, rem, part = False, 0, None
            st, tput = "RUN", 1
        elif (cfg["class"] in SBUF_DIVERT_CLASSES and name not in _TAILS
                and len(sbuf.items) < sbuf.capacity):
            part["diverted"] = True
            yield sbuf.put(part)
            _emit(shared, "DIVERT_SBUF", t, name,
                  {"class": cfg["class"], "part": part["id"]})
            shared["sbuf"]["diverted"] += 1
            held, rem, part = False, 0, None
            st, tput = "RUN", 1
        else:
            st, tput = "BLOCKED", 0
        _transition(shared, idx, name, prev, st, t)
        prev = st
        shared["held"][idx] = part if held else None
        val, _temp, ar = _sample_signal(rng, st, t, cfg, ar)
        obs_row[t], state_row[t], tput_row[t] = val, st, tput
        yield env.timeout(1)


def _agv_xfer(env, agv, rng_agv, part, src, kit, shared, t_req):
    """One tail/SBUF->ASM0-kit transfer: request, hold, release, log wait."""
    hold = int(rng_agv.integers(AGV_STEPS[0], AGV_STEPS[1] + 1))
    req = agv.request()
    yield req
    wait = int(env.now) - t_req
    yield env.timeout(hold)
    t_del = int(env.now)
    agv.release(req)
    if t_del >= T:
        # Episode ended mid-transfer: part stays counted as in-flight
        # (conserved via flow xfer_open bucket), never double-logged.
        return
    kit[part["line"]].append(part)
    shared["flow"]["xfer_open"] -= 1
    shared["agv_waits"].append(
        {"t": t_del, "part": part["id"], "hold": hold, "wait": wait})
    shared["parts"].append(
        {"id": part["id"], "t": t_del, "machine": src, "via": "AGV",
         "disposition": "diverted" if part["diverted"] else "delivered"})
    if src == "SBUF":
        shared["sbuf"]["drained"] += 1
    _emit(shared, "AGV_WAIT", t_del, src,
          {"part": part["id"], "wait": wait, "hold": hold})


def _agv_dispatcher(env, agv, rng_agv, stores, kit, shared):
    """Drain SBUF (first) then tail buffers to kit intake via AGV xfers.

    The AGV queue is bounded (2 in service + 2 queued): beyond that the
    dispatcher holds off spawning, so tail buffers fill and BLOCKED
    backpressure (plus SBUF divert) propagates instead of hiding WIP in an
    unbounded resource queue.
    """
    sbuf = stores["SBUF"]
    tails = [(stores[_TAIL_BUF[n]], n) for n in _TAILS]

    def _gate_open():
        return agv.count + len(agv.queue) < AGV_CAP + 2

    def _spawn(part, src):
        shared["flow"]["xfer_open"] += 1
        env.process(_agv_xfer(env, agv, rng_agv, part, src,
                             kit, shared, int(env.now)))

    while True:
        if int(env.now) >= T:
            return
        if len(sbuf.items) > 0 and _gate_open():
            req = sbuf.get()
            yield req
            _spawn(req.value, "SBUF")
        for store, name in tails:
            if len(store.items) > 0 and _gate_open():
                req = store.get()
                yield req
                _spawn(req.value, name)
        yield env.timeout(1)


def _asm0_process(env, asm01, kit, shared):
    """Kitting: consume 1 part per line per cycle; STARVED unless all present."""
    name, idx = "ASM0", MACHINE_INDEX["ASM0"]
    cfg = MACHINES[name]
    cycle, mttf, mttr = cfg["cycle"], cfg["mttf"], cfg["mttr"]
    rng = shared["noise"][idx]
    obs_row = shared["obs"][idx]
    state_row = shared["states"][idx]
    tput_row = shared["tput"][idx]
    held, rem, batch = False, 0, None
    down_left, ar, prev = 0, 0.0, "RUN"
    for t in range(T):
        detail = {}
        if down_left > 0:
            st, tput = "DOWN", 0
            down_left -= 1
        elif shared["enable_bd"] and shared["fail"].random() < 1.0 / mttf:
            down_left = int(shared["fail"].geometric(1.0 / mttr)) - 1
            st, tput = "DOWN", 0
        elif not held:
            missing = [ln for ln in ("A", "B", "C") if not kit[ln]]
            if missing:
                st, tput = "STARVED", 0
                if prev != "STARVED":
                    detail = {"kit_missing": missing}
            else:
                batch = [kit[ln].pop(0) for ln in ("A", "B", "C")]
                held, rem, st, tput = True, cycle, "RUN", 0
        elif rem > 1:
            rem -= 1
            st, tput = "RUN", 0
        elif len(asm01.items) < asm01.capacity:
            pid = shared["pid"][0]
            shared["pid"][0] += 1
            yield asm01.put({"id": pid, "line": "ASM",
                             "kit": [p["id"] for p in batch]})
            shared["flow"]["asm_created"] += 1
            held, rem, batch = False, 0, None
            st, tput = "RUN", 1
        else:
            st, tput = "BLOCKED", 0
        _transition(shared, idx, name, prev, st, t, detail)
        prev = st
        shared["held"][idx] = {"batch": True} if held else None
        val, _temp, ar = _sample_signal(rng, st, t, cfg, ar)
        obs_row[t], state_row[t], tput_row[t] = val, st, tput
        yield env.timeout(1)


def _asm_mid_process(env, name, up, down, shared):
    """ASM1 join (cycle 6) / ASM2 test (cycle 3, sink + scrap counter)."""
    idx = MACHINE_INDEX[name]
    cfg = MACHINES[name]
    cycle, mttf, mttr = cfg["cycle"], cfg["mttf"], cfg["mttr"]
    rng = shared["noise"][idx]
    obs_row = shared["obs"][idx]
    state_row = shared["states"][idx]
    tput_row = shared["tput"][idx]
    held, rem, part = False, 0, None
    down_left, ar, prev = 0, 0.0, "RUN"
    for t in range(T):
        if down_left > 0:
            st, tput = "DOWN", 0
            down_left -= 1
        elif shared["enable_bd"] and shared["fail"].random() < 1.0 / mttf:
            down_left = int(shared["fail"].geometric(1.0 / mttr)) - 1
            st, tput = "DOWN", 0
        elif not held:
            if len(up.items) > 0:
                req = up.get()
                yield req
                part = req.value
                held, rem, st, tput = True, cycle, "RUN", 0
            else:
                st, tput = "STARVED", 0
        elif rem > 1:
            rem -= 1
            st, tput = "RUN", 0
        elif down is None:
            # ASM2 sink: scrap counting only (no RWK0 routing until T7).
            shared["flow"]["sunk"] += 1
            if part["id"] % 10 == 9:
                shared["flow"]["scrapped"] += 1
                _emit(shared, "REJECT_ROUTE", t, name,
                      {"part": part["id"], "to": "scrap"})
            held, rem, part = False, 0, None
            st, tput = "RUN", 1
        elif len(down.items) < down.capacity:
            yield down.put(part)
            held, rem, part = False, 0, None
            st, tput = "RUN", 1
        else:
            st, tput = "BLOCKED", 0
        _transition(shared, idx, name, prev, st, t)
        prev = st
        shared["held"][idx] = part if held else None
        val, _temp, ar = _sample_signal(rng, st, t, cfg, ar)
        obs_row[t], state_row[t], tput_row[t] = val, st, tput
        yield env.timeout(1)


def _idle_process(env, name, idx, shared):
    """RWK0: no inputs in T6, always STARVED (T7 owns rework flow)."""
    cfg = MACHINES[name]
    rng = shared["noise"][idx]
    obs_row = shared["obs"][idx]
    state_row = shared["states"][idx]
    tput_row = shared["tput"][idx]
    ar, prev = 0.0, "STARVED"
    for t in range(T):
        _transition(shared, idx, name, prev, "STARVED", t)
        prev = "STARVED"
        val, _temp, ar = _sample_signal(rng, "STARVED", t, cfg, ar)
        obs_row[t], state_row[t], tput_row[t] = val, "STARVED", 0
        yield env.timeout(1)


def _monitor(env, stores, order, rows):
    """Record the 31 roster buffer levels after machines act each step."""
    for t in range(T):
        for j, key in enumerate(order):
            rows[j][t] = len(stores[key].items) if key in stores else 0
        yield env.timeout(1)


def run_episode(seed: int, fault: dict | None = None, *,
                enable_natural_breakdown: bool = True) -> dict:
    """Run one episode; passed fault validated + echoed only (T7 applies it)."""
    fault = _validate(seed, fault)
    noise, rng_agv, fail = _spawn_streams(seed)
    env = simpy.Environment()
    agv = simpy.Resource(env, capacity=AGV_CAP)
    stores = {n: simpy.Store(env, capacity=c) for n, c in BUFFERS.items()}
    stores["_C7TAIL"] = simpy.Store(
        env, capacity=MACHINES["C7"]["buffer_cap"])  # AGV drains this
    assert len(MACHINES) == N_MACHINES and len(BUFFERS) == N_BUFFERS
    order = sorted(MACHINE_INDEX, key=MACHINE_INDEX.get)
    shared = {
        "noise": noise, "fail": fail, "enable_bd": enable_natural_breakdown,
        "obs": [[0.0] * T for _ in range(N_MACHINES)],
        "states": [["RUN"] * T for _ in range(N_MACHINES)],
        "tput": [[0] * T for _ in range(N_MACHINES)],
        "events": [], "agv_waits": [],
        "parts": [], "pid": [0],
        "held": [None] * N_MACHINES,
        "flow": {"line_created": 0, "asm_created": 0, "sunk": 0,
                 "scrapped": 0, "xfer_open": 0},
        "sbuf": {"diverted": 0, "drained": 0},
    }
    kit = {"A": [], "B": [], "C": []}
    edges = _line_edges()
    for name in _LINES:
        up_key, down_key = edges[name]
        env.process(_line_process(env, {
            "name": name, "idx": MACHINE_INDEX[name],
            "up": stores[up_key] if up_key else None,
            "down": stores[down_key], "sbuf": stores["SBUF"]}, shared))
    env.process(_asm0_process(env, stores["ASM01"], kit, shared))
    env.process(_asm_mid_process(env, "ASM1", stores["ASM01"],
                                 stores["ASM12"], shared))
    env.process(_asm_mid_process(env, "ASM2", stores["ASM12"], None, shared))
    for name in _IDLE:
        env.process(_idle_process(env, name, MACHINE_INDEX[name], shared))
    env.process(_agv_dispatcher(env, agv, rng_agv, stores, kit, shared))
    buf_order = list(BUFFERS)
    buf_rows = [[0] * T for _ in range(N_BUFFERS)]
    env.process(_monitor(env, stores, buf_order, buf_rows))
    env.run(until=T)
    # Post-run store census (exact WIP audit — the channel-6 series tail can
    # miss last-step puts/gets that land after the monitor's final record).
    store_final = {k: len(stores[k].items) for k in buf_order}
    store_final["_C7TAIL"] = len(stores["_C7TAIL"].items)
    sbuf_row = buf_rows[buf_order.index("SBUF")]
    sbuf_final = len(stores["SBUF"].items)
    high_steps = [t for t in range(T) if sbuf_row[t] >= _SBUF_HIGH]
    sbuf_stats = {
        "diverted": shared["sbuf"]["diverted"],
        "drained": shared["sbuf"]["drained"],
        "max_occupancy": max(sbuf_row),
        "high_util": max(sbuf_row) >= _SBUF_HIGH,
        "high_util_steps": high_steps,
        "final": sbuf_final,
        "cap": SBUF_CAP,
    }
    held_line = sum(1 for i, n in enumerate(order)
                    if n in _LINES and shared["held"][i] is not None)
    flow_stats = {
        "line_created": shared["flow"]["line_created"],
        "asm_created": shared["flow"]["asm_created"],
        "sunk": shared["flow"]["sunk"],
        "scrapped": shared["flow"]["scrapped"],
        "xfer_open": shared["flow"]["xfer_open"],
        "held_line": held_line,
        "held_asm0_batch": 1 if shared["held"][MACHINE_INDEX["ASM0"]] else 0,
        "held_asm12": sum(1 for n in ("ASM1", "ASM2")
                          if shared["held"][MACHINE_INDEX[n]] is not None),
        "kit_A": len(kit["A"]), "kit_B": len(kit["B"]),
        "kit_C": len(kit["C"]),
        "c7tail": len(stores["_C7TAIL"].items),
        "store_final": store_final,
    }
    return {
        "seed": seed, "T": T, "cal_win": CAL_WIN, "obs": shared["obs"],
        "states": shared["states"], "buffers": buf_rows,
        "throughput": shared["tput"], "events": shared["events"],
        "sbuf_stats": sbuf_stats, "flow_stats": flow_stats,
        "agv_waits": shared["agv_waits"],
        "parts": shared["parts"], "faults": [fault] if fault else [],
    }


def run_calibration(seed: int):
    """Return (120, 32) clean window: breakdowns off, first CAL_WIN steps."""
    rec = run_episode(seed, None, enable_natural_breakdown=False)
    return np.asarray(rec["obs"], dtype=float)[:, :CAL_WIN].T


def build_faults(seed: int = 12345) -> list[dict]:
    """Build fault manifest for master seed. T7 owns this."""
    raise NotImplementedError("T7 owns build_faults")


_CAL_SEEDS = (7, 11, 13)
_F21_SHAPE = {"id": "F-21", "class": "drift", "origin": "B5",
              "t0": 150, "dur": 12, "mag_sigma": 5.2}


def _calibrate(path):
    """Time clean + F-21-shape episodes (clean signals, timing only)."""
    episodes = []
    for seed in _CAL_SEEDS:
        for tag, fault in (("clean", None), ("F-21-drift-shape", _F21_SHAPE)):
            start = time.perf_counter()
            run_episode(seed, dict(fault) if fault else None)
            wall = time.perf_counter() - start
            episodes.append({"seed": seed, "fault": tag, "wall_s": wall,
                             "enable_natural_breakdown": True,
                             "faultdev_applied": False})
    mean = sum(e["wall_s"] for e in episodes) / len(episodes)
    payload = {"mean_per_episode_s": mean, "seeds": list(_CAL_SEEDS),
               "episodes_timed": len(episodes), "episodes": episodes}
    with open(path, "w") as fh:
        json.dump(payload, fh, indent=2)
    print(f"mean_per_episode_s={mean:.4f} episodes={len(episodes)} -> {path}")


if __name__ == "__main__":
    _calibrate(sys.argv[1] if len(sys.argv) > 1 else
               ".omo/evidence/task-5-minipro-16-m01-twin.calibration.json")
