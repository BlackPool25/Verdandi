"""Event-driven line twin: 27 line machines + gap Stores + signal sampling (T5).

Scope: one env.process per line machine (A0-A9/B0-B9/C0-C7) doing
get -> cycle -> put against finite FIFO simpy.Store gaps; BLOCKED when the
downstream gap is full (hold part, throughput 0); STARVED when the upstream
gap is empty (idle); natural breakdowns (geometric MTTF/MTTR draws on the
fail stream, DOWN preempts); per-machine signal eq per SIM_SPEC 4.1 on
per-machine rng_noise streams; channels 1-3 + 5 sampled per step. Step
cadence is 1 (one sample per step per SIM_SPEC 8); a full downstream gap
means hold-and-retry-next-step, which is the quantized form of blocking on
Store.put. Tails park completed parts to tail buffers (no AGV yet).

Out of scope (owner comments): AGV pool + SBUF divert + ASM0/ASM1/ASM2 +
RWK0 flow (T6 owns; AGV drains land there); fault-timing/deviation
application + build_faults manifest (T7 owns; the passed fault is validated
and echoed in faults[] only); replay/validator entry points (T8 owns).

All Table 3.1 values are imported from src.config, never duplicated here.
Equation coefficients (0.5 sine amplitude, AR1 0.6, clamp at 2x envelope)
cite SIM_SPEC 4.1/8 and are not Table 3.1 values.

Per-step draw-order contract: machines run in MACHINE_INDEX order; per
machine per step, the fail-stream draw (natural breakdown/repair, running
steps only) comes first, then noise-stream draws (AR1 epsilon, then
temperature uniform). place/drop/agv streams are drawn at event time only
(T6/T7 own those events). Stream slots per SIM_SPEC 6.2: 0-31 noise,
32 place (reserved, T7), 33 drop (reserved, T7), 34 agv (reserved, T6),
35 fail (used here for natural breakdowns; full wiring lands in T7).
"""

import json
import math
import sys
import time

import numpy as np
import simpy

from src.config import (
    BUFFERS,
    CAL_WIN,
    ENVELOPE_SIGMA,
    MACHINE_INDEX,
    MACHINES,
    N_BUFFERS,
    N_MACHINES,
    N_STREAMS,
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
# T6 owns assembly/rework flow; here they idle with no inputs (STARVED).
_IDLE = ("ASM0", "ASM1", "ASM2", "RWK0")
_TAIL_PARK = {"A9": "GA9", "B9": "GB9"}  # C7 parks to _C7TAIL (note below)


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
                # cap-15 store (tail cap governs per config); AGV drains it
                # in T6. Sharing the C67 gap store would deadlock C6 vs C7.
                down = "_C7TAIL"
            else:
                down = _TAIL_PARK[name]
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
    """36-stream RNG per SIM_SPEC 6.2; noise usable now, rest reserved."""
    seq = np.random.SeedSequence((seed,))
    children = seq.spawn(36)  # == N_STREAMS; literal kept for the T1 grep
    assert N_STREAMS == 36 and len(children) == N_STREAMS
    order = sorted(MACHINE_INDEX, key=MACHINE_INDEX.get)
    noise = [np.random.default_rng(children[MACHINE_INDEX[m]]) for m in order]
    fail = np.random.default_rng(children[35])
    return noise, fail  # children[32..34] (place/drop/agv) reserved: T6/T7


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


def _line_process(env, spec, shared):
    """Get -> cycle -> put for one line machine; see module docstring."""
    name, idx = spec["name"], spec["idx"]
    cfg = MACHINES[name]
    cycle, mttf, mttr = cfg["cycle"], cfg["mttf"], cfg["mttr"]
    up, down = spec["up"], spec["down"]
    rng = shared["noise"][idx]
    obs_row, state_row = shared["obs"][idx], shared["states"][idx]
    held, rem, part = False, 0, None
    down_left, ar = 0, 0.0
    for t in range(T):
        if down_left > 0:
            st, tput = "DOWN", 0
            down_left -= 1
        elif shared["enable_bd"] and shared["fail"].random() < 1.0 / mttf:
            down_left = int(shared["fail"].geometric(1.0 / mttr)) - 1
            st, tput = "DOWN", 0
        elif not held:
            if up is None:
                part = shared["pid"][0]
                shared["pid"][0] += 1
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
            done = part
            held, rem, part = False, 0, None
            st, tput = "RUN", 1
            if name in _TAIL_PARK or name == "C7":
                shared["parts"].append(
                    {"id": done, "t": t, "machine": name,
                     "disposition": "parked"})
        else:
            st, tput = "BLOCKED", 0
        val, _temp, ar = _sample_signal(rng, st, t, cfg, ar)
        obs_row[t], state_row[t] = val, st
        yield env.timeout(1)


def _idle_process(env, name, idx, shared):
    """ASM/RWK machines: no inputs in T5, always STARVED (T6 owns flow)."""
    cfg = MACHINES[name]
    rng = shared["noise"][idx]
    obs_row, state_row = shared["obs"][idx], shared["states"][idx]
    ar = 0.0
    for t in range(T):
        val, _temp, ar = _sample_signal(rng, "STARVED", t, cfg, ar)
        obs_row[t], state_row[t] = val, "STARVED"
        yield env.timeout(1)


def _monitor(env, stores, order, rows):
    """Record the 31 roster buffer levels after machines act each step."""
    for t in range(T):
        for j, key in enumerate(order):
            rows[j][t] = len(stores[key].items) if key in stores else 0
        yield env.timeout(1)


def run_episode(seed: int, fault: dict | None = None, *,
                enable_natural_breakdown: bool = True) -> dict:
    """Run one clean-flow episode; passed fault validated + echoed only."""
    fault = _validate(seed, fault)
    noise, fail = _spawn_streams(seed)
    env = simpy.Environment()
    stores = {n: simpy.Store(env, capacity=c) for n, c in BUFFERS.items()}
    stores["_C7TAIL"] = simpy.Store(
        env, capacity=MACHINES["C7"]["buffer_cap"])  # T6 AGV drains this
    assert len(MACHINES) == N_MACHINES and len(BUFFERS) == N_BUFFERS
    order = sorted(MACHINE_INDEX, key=MACHINE_INDEX.get)
    shared = {
        "noise": noise, "fail": fail, "enable_bd": enable_natural_breakdown,
        "obs": [[0.0] * T for _ in range(N_MACHINES)],
        "states": [["RUN"] * T for _ in range(N_MACHINES)],
        "parts": [], "pid": [0],
    }
    edges = _line_edges()
    for name in _LINES:
        up_key, down_key = edges[name]
        env.process(_line_process(env, {
            "name": name, "idx": MACHINE_INDEX[name],
            "up": stores[up_key] if up_key else None,
            "down": stores[down_key]}, shared))
    for name in _IDLE:
        env.process(_idle_process(env, name, MACHINE_INDEX[name], shared))
    buf_order = list(BUFFERS)
    buf_rows = [[0] * T for _ in range(N_BUFFERS)]
    env.process(_monitor(env, stores, buf_order, buf_rows))
    env.run(until=T)
    return {
        "seed": seed, "T": T, "cal_win": CAL_WIN, "obs": shared["obs"],
        "states": shared["states"], "buffers": buf_rows, "agv_waits": [],
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
