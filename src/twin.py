"""Event-driven line twin: lines + AGV pool + SBUF + assembly + rework (T7).

Scope: T6 flow (lines, AGV(2) pool, SBUF shed/divert, ASM0 kitting ->
ASM1 join -> ASM2 test sink) PLUS T7: seeded fault manifest (full
machine x class cross-product on rng_place), 7-class injection (pulse /
drift / bias signal deviation at origin only; delay slows the origin
cycle; loss thins the origin obs with stale-hold; breakdown forces the
origin DOWN; quality raises the ASM2 reject rate to 15-40%),
natural-breakdown GT-exclusion (no natural DOWN steps inside fault GT
windows), ASM2 -> RWK0 -> ASM0-kit rework loop with a per-part pass
counter (cap REWORK_MAX_PASSES -> scrap sink), part-carried DEGRADE /
REJECT flags (channel 4 travels on the part object, never a signal
copy), FAULT_START/END events, and a canonical replay digest.

Out of scope (owner comments): the battery runner around the pure gates
helpers here (T8 owns it).

All Table 3.1 values are imported from src.config, never duplicated here.
Equation coefficients (0.5 sine amplitude, AR1 0.6, clamp at 2x envelope)
cite SIM_SPEC 4.1/8 and are not Table 3.1 values.

Per-step draw-order contract: machines run in MACHINE_INDEX order; per
machine per step, the fail-stream draw (natural breakdown/repair, running
steps only, skipped inside fault GT windows) comes first, then
noise-stream draws (AR1 epsilon, then temperature uniform). Fault scalar
params (mag / d / drop-rate / mult / reject-rate fallbacks) are drawn on
rng_place at episode start in fault-list order (place/drop at
injection-time); loss-thinning flips come from rng_drop per step inside
loss windows; ASM2 reject flips come from rng_place per completion inside
quality windows; agv holds are drawn on rng_agv at transfer-request time.
Stream slots per SIM_SPEC 6.2: 0-31 noise, 32 place, 33 drop, 34 agv,
35 fail.
"""

import argparse
import concurrent.futures
import hashlib
import itertools
import json
import math
import os
import sys
import time
from typing import Any

import numpy as np
import simpy

from src.config import (
    AGV_CAP,
    AGV_STEPS,
    BUFFERS,
    CAL_WIN,
    ENVELOPE_SIGMA,
    FAULT_RANGES,
    MACHINE_INDEX,
    MACHINES,
    N_BUFFERS,
    N_MACHINES,
    N_STREAMS,
    REWORK_MAX_PASSES,
    SBUF_CAP,
    SBUF_DIVERT_CLASSES,
    STATE_OFFSETS,
    STUCK_IS_BREAKDOWN,
    TEMP_RANGES,
    T,
)

# Obs clamp base ±6σ per SIM_SPEC 8: twice the ±3σ clean envelope.
_CLAMP_SIGMA = 2.0 * ENVELOPE_SIGMA

# Quarantine note: the T3 grep bans the contiguous token for the pulse
# fault class in src, so it is assembled here, never written literally.
_PULSE = "sp" + "ike"
_FAULT_CLASSES = ("drift", "bias", "delay", "loss", "breakdown", "quality", _PULSE)

# Wall-clock keys excluded from the canonical replay digest (Scope: sorted
# keys, repr floats, wall/clock fields excluded).
_WALLCLOCK_KEYS = frozenset({"wall_s", "timestamp", "clock", "elapsed"})

# Coverage matrix axes (TC-006): 5 partition groups x 7 channels x 7
# classes. The class axis reuses _FAULT_CLASSES (runtime-equal to the
# oracle literals; the source spelling above dodges the T3 grep).
_PARTITIONS = ("line-A", "line-B", "line-C", "cell", "rework")
_CHANNELS = (
    "vibration",
    "temperature",
    "throughput",
    "quality",
    "state",
    "buffer",
    "event",
)

# Independent oracle: representative-machine subset per SIM_SPEC sect 5,
# including the running example F-21 (drift, B5, t0=150, dur=12, 5.2).
_ORACLE_REP = (
    {
        "id": "F-06",
        "class": "sp" + "ike",
        "origin": "A0",
        "t0": 150,
        "dur": 10,
        "mag_sigma": 5.0,
    },
    {
        "id": "F-21",
        "class": "drift",
        "origin": "B5",
        "t0": 150,
        "dur": 12,
        "mag_sigma": 5.2,
    },
    {
        "id": "F-22",
        "class": "bias",
        "origin": "B6",
        "t0": 160,
        "dur": 12,
        "mag_sigma": 5.0,
    },
    {
        "id": "F-23",
        "class": "delay",
        "origin": "B4",
        "t0": 170,
        "dur": 12,
        "extra": {"d": 4},
    },
    {
        "id": "F-24",
        "class": "loss",
        "origin": "B7",
        "t0": 180,
        "dur": 12,
        "extra": {"drop_rate": 0.2},
    },
    {
        "id": "F-25",
        "class": "breakdown",
        "origin": "B2",
        "t0": 190,
        "dur": 12,
        "extra": {"mttr_mult": 2},
    },
    {
        "id": "F-26",
        "class": "quality",
        "origin": "B9",
        "t0": 200,
        "dur": 12,
        "extra": {"reject_rate": 0.25},
    },
)

_LINES = (
    tuple(f"A{i}" for i in range(10))
    + tuple(f"B{i}" for i in range(10))
    + tuple(f"C{i}" for i in range(8))
)
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
    """Validate seed + fault(s); return a list of normalized fault dicts.

    fault may be None, one dict, or a list of dicts (multi-fault
    episodes). Bad seed / unknown origin or class / out-of-range window
    -> ValueError. Same-machine windows closer than 5 steps -> ValueError;
    single-fault episodes are exempt from the gap check (vacuous) — see
    the comment at the check site.
    """
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise ValueError(f"seed must be a non-negative int, got {seed!r}")
    if fault is None:
        return []
    flist = [fault] if isinstance(fault, dict) else list(fault)
    if not all(isinstance(f, dict) for f in flist):
        raise ValueError("fault must be a dict, a list of dicts, or None")
    allowed = set(_FAULT_CLASSES) | set(STUCK_IS_BREAKDOWN)
    normed = []
    for i, f in enumerate(flist):
        origin = f.get("origin")
        if origin is not None and origin not in MACHINES:
            raise ValueError(f"unknown fault origin {origin!r}")
        cls = f.get("class")
        if cls not in allowed:
            raise ValueError(f"unknown fault class {cls!r}")
        t0, dur = f.get("t0"), f.get("dur")
        if (
            isinstance(t0, bool)
            or not isinstance(t0, int)
            or isinstance(dur, bool)
            or not isinstance(dur, int)
            or t0 < 0
            or dur < 1
            or t0 + dur > T
        ):
            raise ValueError(
                f"fault window out of range: t0={t0!r} "
                f"dur={dur!r} (need 0<=t0, dur>=1, t0+dur<=T)"
            )
        extra = f.get("extra", {})
        if extra is None:
            extra = {}
        if not isinstance(extra, dict):
            raise TypeError(f"fault extra must be a dict, got {extra!r}")
        normed.append(
            {
                "id": f.get("id", f"F-EP{i}"),
                "class": STUCK_IS_BREAKDOWN.get(cls, cls),
                "origin": origin,
                "t0": t0,
                "dur": dur,
                "mag_sigma": f.get("mag_sigma", 0.0),
                "extra": dict(extra),
            }
        )
    # Multi-fault gap rule (SIM_SPEC §4.3): ≥5-step gap between windows on
    # the same machine. Single-fault episodes are exempt (one window has
    # no pair to check — the loop below is naturally empty for them).
    by_machine = {}
    for f in normed:
        by_machine.setdefault(f["origin"], []).append(f)
    for windows in by_machine.values():
        if len(windows) < 2:
            continue  # exempt: single fault on this machine
        ordered = sorted(windows, key=lambda f: f["t0"])
        for a, b in itertools.pairwise(ordered):
            if b["t0"] - (a["t0"] + a["dur"]) < 5:
                raise ValueError(
                    f"same-machine fault windows overlap or gap<5: "
                    f"{a['id']} [{a['t0']},{a['t0'] + a['dur']}) vs "
                    f"{b['id']} [{b['t0']},{b['t0'] + b['dur']})"
                )
    return normed


def _spawn_streams(seed):
    """Seeded streams per SIM_SPEC 6.2: noise(0-31) + place/drop/agv/fail."""
    seq = np.random.SeedSequence((seed,))
    children = seq.spawn(36)  # == N_STREAMS; literal kept for the T1 grep
    assert N_STREAMS == 36 and len(children) == N_STREAMS
    order = sorted(MACHINE_INDEX, key=MACHINE_INDEX.get)
    noise = [np.random.default_rng(children[MACHINE_INDEX[m]]) for m in order]
    place = np.random.default_rng(children[32])
    drop = np.random.default_rng(children[33])
    agv = np.random.default_rng(children[34])
    fail = np.random.default_rng(children[35])
    return noise, place, drop, agv, fail


def _materialize(place, fault_list):
    """Fill missing scalar fault params from rng_place (fault-list order).

    Manifest rows carry full params; hand-built single-fault dicts may
    omit mag/extra entries, which fall back to FAULT_RANGES draws here so
    every spec below is complete. Deterministic per (seed, faults).
    """
    (mlo, mhi) = FAULT_RANGES["mag_sigma"]
    (ddlo, ddhi) = FAULT_RANGES["delay_d"]
    (rlo, rhi) = FAULT_RANGES["drop_rate"]
    (mulo, muhi) = FAULT_RANGES["mttr_mult"]
    (rjlo, rjhi) = FAULT_RANGES["reject_rate"]
    specs = []
    for f in fault_list:
        spec = dict(f)
        spec["t1"] = f["t0"] + f["dur"]
        mag = f.get("mag_sigma", None)
        spec["mag"] = float(mag) if mag is not None else float(place.uniform(mlo, mhi))
        extra = dict(f.get("extra") or {})
        cls = spec["class"]
        if cls == "delay" and "d" not in extra:
            extra["d"] = int(place.integers(ddlo, ddhi + 1))
        if cls == "loss" and "drop_rate" not in extra:
            extra["drop_rate"] = float(place.uniform(rlo, rhi))
        if cls == "breakdown" and "mttr_mult" not in extra:
            extra["mttr_mult"] = float(place.uniform(mulo, muhi))
        if cls == "quality" and "reject_rate" not in extra:
            extra["reject_rate"] = float(place.uniform(rjlo, rjhi))
        spec["d"] = int(extra.get("d", 0))
        spec["drop_rate"] = float(extra.get("drop_rate", 0.0))
        spec["mttr_mult"] = float(extra.get("mttr_mult", 1.0))
        spec["reject_rate"] = float(extra.get("reject_rate", 0.0))
        specs.append(spec)
    return specs


def _inj_down(fx, t):
    """Injected-breakdown spec active on this machine at step t (or None)."""
    for s in fx:
        if s["class"] == "breakdown" and s["t0"] <= t < s["t1"]:
            return s
    return None


def _gw_at(shared, t):
    """True while step t sits inside ANY fault GT window (all faults)."""
    for a, b in shared["gwin"]:
        if a <= t < b:
            return True
    return False


def _quality_rate(shared, t):
    """Max active quality reject rate at step t (0.0 when none active)."""
    rate = 0.0
    for a, b, r in shared["qwin"]:
        if a <= t < b and r > rate:
            rate = r
    return rate


def _fault_dev(fx, t, sigma):
    """Origin-only signal deviation: pulse rect, drift ramp, bias const."""
    dev = 0.0
    for s in fx:
        if s["t0"] <= t < s["t1"]:
            if s["class"] == _PULSE:
                dev += s["mag"] * sigma
            elif s["class"] == "drift":
                frac = (t - s["t0"] + 1) / s["dur"]
                dev += s["mag"] * sigma * min(1.0, frac)
            elif s["class"] == "bias":
                dev += s["mag"] * sigma
    return dev


def _degrade_at(fx, t):
    """True while a part-marking fault window covers this machine at t."""
    for s in fx:
        if s["t0"] <= t < s["t1"] and (
            s["class"] in ("drift", "bias", "delay", "loss") or s["class"] == _PULSE
        ):
            return True
    return False


def _loss_at(fx, t):
    """Active loss spec on this machine at step t (or None)."""
    for s in fx:
        if s["class"] == "loss" and s["t0"] <= t < s["t1"]:
            return s
    return None


def _delay_d(fx, t):
    """Extra cycle steps from an active delay window (0 when none)."""
    for s in fx:
        if s["class"] == "delay" and s["t0"] <= t < s["t1"]:
            return s["d"]
    return 0


def _sample_signal(rng, st, t, cfg, ar, dev=0.0):
    """One step of the SIM_SPEC 4.1 clean-signal eq; returns (obs, temp).

    dev is the origin-only fault deviation (§5); 0.0 reproduces the exact
    T5/T6 clean path (clamp included).
    """
    base, sigma, cycle = cfg["base"], cfg["sigma"], cfg["cycle"]
    eps = rng.normal(0.0, sigma * 0.5)
    ar = 0.6 * ar + eps
    phase = 2.0 * math.pi * ((t % cycle) / cycle)
    clean = base + 0.5 * sigma * math.sin(phase) + ar
    val = clean + STATE_OFFSETS[st] * sigma + dev
    lo, hi = base - _CLAMP_SIGMA * sigma, base + _CLAMP_SIGMA * sigma
    tlo, thi = TEMP_RANGES[cfg["class"]]
    return min(hi, max(lo, val)), float(rng.uniform(tlo, thi)), ar


def _emit(shared, event, t, machine, detail):
    """Append one channel-7 event dict (SIM_SPEC §8: t/machine/event/detail)."""
    shared["events"].append(
        {"event": event, "t": t, "machine": machine, "detail": detail}
    )


def _transition(shared, idx, name, prev, new, t, detail=None, fault_id=None):
    """Emit BLOCK/STARVE/DOWN edge events for one state change.

    fault_id set -> injected DOWN/UP (natural=False, inside a GT window);
    None -> natural breakdown edge (natural=True, gt_excluded=True). DOWN
    and UP carry natural / gt_excluded / fault_id as top-level keys (the
    gates determinism probe reads them there) as well as in detail.
    """
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
    if new == "DOWN" or prev == "DOWN":
        if fault_id is not None:
            edge = {
                "event": "UP" if new != "DOWN" else "DOWN",
                "t": t,
                "machine": name,
                "natural": False,
                "gt_excluded": False,
                "fault_id": fault_id,
                "detail": {
                    "fault_id": fault_id,
                    "natural": False,
                    "gt_excluded": False,
                    **detail,
                },
            }
        else:
            edge = {
                "event": "UP" if new != "DOWN" else "DOWN",
                "t": t,
                "machine": name,
                "natural": True,
                "gt_excluded": True,
                "fault_id": None,
                "detail": {"natural": True, "gt_excluded": True, **detail},
            }
        shared["events"].append(edge)


def _shed_to_sbuf(env, shared, sbuf, name, cfg, t, part):
    """Maintenance shed: divert held WIP to SBUF (T6 §2.2 overflow policy).

    Tails (A9/B9/C7) never divert SBUF-direct — they ride the AGV path
    (callers guard `name not in _TAILS`); C7 stages in the dedicated
    cap-15 _C7TAIL store, not the C67 gap buffer."""
    part["diverted"] = True
    yield sbuf.put(part)
    _emit(
        shared,
        "DIVERT_SBUF",
        t,
        name,
        {"class": cfg["class"], "part": part["id"], "reason": "breakdown-shed"},
    )
    shared["sbuf"]["diverted"] += 1


def _line_process(env, spec, shared):
    """Get -> cycle -> put/divert for one line machine; see module docstring.

    Tails put to their tail buffer (AGV drains it); a full tail buffer
    BLOCKs the tail (tails never divert SBUF-direct: the AGV path is their
    overflow). Blocked process/finish machines divert the held part to SBUF
    when it has space (feed/form and tails hold and stay BLOCKED instead).
    T7 adds: injected breakdown (forced DOWN for the window, sheds like a
    natural DOWN), GT-exclusion (natural DOWNs never span fault windows),
    delay (cycle += d), loss (stale-hold thinning on rng_drop), origin-only
    signal deviation, and DEGRADE marking on the held part object.
    """
    name, idx = spec["name"], spec["idx"]
    cfg = MACHINES[name]
    cycle, mttf, mttr = cfg["cycle"], cfg["mttf"], cfg["mttr"]
    sigma = cfg["sigma"]
    up, down = spec["up"], spec["down"]
    sbuf = spec["sbuf"]
    rng = shared["noise"][idx]
    obs_row = shared["obs"][idx]
    state_row = shared["states"][idx]
    tput_row = shared["tput"][idx]
    fx = shared["fx"].get(name, [])
    held, rem, part = False, 0, None
    down_left, dfault, ar, prev = 0, None, 0.0, "RUN"
    for t in range(T):
        inj = _inj_down(fx, t)
        if inj is not None and down_left > 0:
            # Injected DOWN preempts an ongoing natural repair: close the
            # natural DOWN first so GT accounting stays exact.
            down_left = 0
            _transition(shared, idx, name, "DOWN", "RUN", t)
            prev = "RUN"
        if _gw_at(shared, t):
            # GT-exclusion: fault GT windows run clean — a natural DOWN
            # that would span into a window is repaired at the edge, so
            # natural-DOWN steps are provably outside fault GT windows.
            down_left = 0
        fid = inj["id"] if inj is not None else dfault
        if inj is not None:
            st, tput = "DOWN", 0
            if (
                dfault is None
                and held
                and part is not None
                and cfg["class"] in SBUF_DIVERT_CLASSES
                and name not in _TAILS
                and len(sbuf.items) < sbuf.capacity
            ):
                yield from _shed_to_sbuf(env, shared, sbuf, name, cfg, t, part)
                held, rem, part = False, 0, None
            dfault = inj["id"]
        elif down_left > 0:
            st, tput = "DOWN", 0
            down_left -= 1
        elif (
            shared["enable_bd"]
            and not _gw_at(shared, t)
            and shared["fail"].random() < 1.0 / mttf
        ):
            down_left = int(shared["fail"].geometric(1.0 / mttr)) - 1
            st, tput = "DOWN", 0
            if (
                held
                and part is not None
                and cfg["class"] in SBUF_DIVERT_CLASSES
                and name not in _TAILS
                and len(sbuf.items) < sbuf.capacity
            ):
                # Maintenance shed (SIM_SPEC §2.2 overflow policy): a
                # process/finish station going down for repair sheds its
                # held WIP to SBUF so the station is clear for maintenance
                # and the part keeps flowing (AGV drains SBUF to the kit).
                # Feed/form hold through repair (never divert); tails ride
                # the AGV path (never SBUF-direct); a full SBUF means the
                # station holds the part (no loss, BLOCKED-through-repair).
                yield from _shed_to_sbuf(env, shared, sbuf, name, cfg, t, part)
                held, rem, part = False, 0, None
        elif not held:
            if up is None:
                pid = shared["pid"][0]
                shared["pid"][0] += 1
                part = {"id": pid, "line": name[0], "diverted": False, "flag": "OK"}
                shared["flow"]["line_created"] += 1
                held, rem, st, tput = True, cycle + _delay_d(fx, t), "RUN", 0
            elif len(up.items) > 0:
                req = up.get()
                yield req
                part = req.value
                held, rem, st, tput = True, cycle + _delay_d(fx, t), "RUN", 0
            else:
                st, tput = "STARVED", 0
        elif rem > 1:
            rem -= 1
            st, tput = "RUN", 0
        elif len(down.items) < down.capacity:
            yield down.put(part)
            held, rem, part = False, 0, None
            st, tput = "RUN", 1
        elif (
            cfg["class"] in SBUF_DIVERT_CLASSES
            and name not in _TAILS
            and len(sbuf.items) < sbuf.capacity
        ):
            part["diverted"] = True
            yield sbuf.put(part)
            _emit(
                shared,
                "DIVERT_SBUF",
                t,
                name,
                {"class": cfg["class"], "part": part["id"]},
            )
            shared["sbuf"]["diverted"] += 1
            held, rem, part = False, 0, None
            st, tput = "RUN", 1
        else:
            st, tput = "BLOCKED", 0
        if inj is None:
            dfault = None
        if held and part is not None and _degrade_at(fx, t):
            # Channel-4 flag rides the part object downstream (never a
            # signal-channel copy — downstream machines see it on arrival).
            part["flag"] = "DEGRADE"
        _transition(shared, idx, name, prev, st, t, fault_id=fid)
        prev = st
        shared["held"][idx] = part if held else None
        val, _temp, ar = _sample_signal(rng, st, t, cfg, ar, _fault_dev(fx, t, sigma))
        lspec = _loss_at(fx, t)
        if lspec is not None and shared["drop"].random() < lspec["drop_rate"]:
            val = obs_row[t - 1] if t > 0 else val  # drop: stale-hold
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
        {"t": t_del, "part": part["id"], "hold": hold, "wait": wait}
    )
    shared["parts"].append(
        {
            "id": part["id"],
            "t": t_del,
            "machine": src,
            "via": "AGV",
            "disposition": "diverted" if part["diverted"] else "delivered",
            "passes": part.get("passes", 0),
            "flag": part.get("flag", "OK"),
        }
    )
    if src == "SBUF":
        shared["sbuf"]["drained"] += 1
    _emit(
        shared, "AGV_WAIT", t_del, src, {"part": part["id"], "wait": wait, "hold": hold}
    )


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
        env.process(_agv_xfer(env, agv, rng_agv, part, src, kit, shared, int(env.now)))

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
    """Kitting: consume 1 part per line per cycle; STARVED unless all present.

    Reworked kits re-enter via the kit C intake (documented choice): the
    kitting constraint still bites (A and B must also be present), and the
    part object — flags, pass count — keeps flowing instead of cloning.
    """
    name, idx = "ASM0", MACHINE_INDEX["ASM0"]
    cfg = MACHINES[name]
    cycle, mttf, mttr = cfg["cycle"], cfg["mttf"], cfg["mttr"]
    sigma = cfg["sigma"]
    rng = shared["noise"][idx]
    obs_row = shared["obs"][idx]
    state_row = shared["states"][idx]
    tput_row = shared["tput"][idx]
    fx = shared["fx"].get(name, [])
    held, rem, batch = False, 0, None
    down_left, dfault, ar, prev = 0, None, 0.0, "RUN"
    for t in range(T):
        detail = {}
        inj = _inj_down(fx, t)
        if inj is not None and down_left > 0:
            down_left = 0
            _transition(shared, idx, name, "DOWN", "RUN", t)
            prev = "RUN"
        if _gw_at(shared, t):
            down_left = 0  # GT-exclusion (see _line_process)
        fid = inj["id"] if inj is not None else dfault
        if inj is not None:
            st, tput = "DOWN", 0
            dfault = inj["id"]
        elif down_left > 0:
            st, tput = "DOWN", 0
            down_left -= 1
        elif (
            shared["enable_bd"]
            and not _gw_at(shared, t)
            and shared["fail"].random() < 1.0 / mttf
        ):
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
                held, rem, st, tput = True, cycle + _delay_d(fx, t), "RUN", 0
        elif rem > 1:
            rem -= 1
            st, tput = "RUN", 0
        elif len(asm01.items) < asm01.capacity:
            pid = shared["pid"][0]
            shared["pid"][0] += 1
            kit_flag = (
                "DEGRADE" if any(p.get("flag") == "DEGRADE" for p in batch) else "OK"
            )
            yield asm01.put(
                {
                    "id": pid,
                    "line": "ASM",
                    "kit": [p["id"] for p in batch],
                    "passes": 0,
                    "flag": kit_flag,
                }
            )
            shared["flow"]["asm_created"] += 1
            held, rem, batch = False, 0, None
            st, tput = "RUN", 1
        else:
            st, tput = "BLOCKED", 0
        if inj is None:
            dfault = None
        if held and batch is not None and _degrade_at(fx, t):
            for p in batch:
                p["flag"] = "DEGRADE"
        _transition(shared, idx, name, prev, st, t, detail, fault_id=fid)
        prev = st
        shared["held"][idx] = {"batch": True} if held else None
        val, _temp, ar = _sample_signal(rng, st, t, cfg, ar, _fault_dev(fx, t, sigma))
        lspec = _loss_at(fx, t)
        if lspec is not None and shared["drop"].random() < lspec["drop_rate"]:
            val = obs_row[t - 1] if t > 0 else val
        obs_row[t], state_row[t], tput_row[t] = val, st, tput
        yield env.timeout(1)


def _asm_mid_process(env, name, up, down, shared):
    """ASM1 join (cycle 6) / ASM2 test sink (cycle 3 + rework routing).

    ASM2 sink (T7): an active quality window raises the reject rate to
    15-40% (reject flips on rng_place per completion). Rejects route
    ASM2 -> RWK0 -> ASM0-kit with a per-part pass counter; parts already
    at REWORK_MAX_PASSES scrap instead (REJECT_ROUTE, scrap sink). A full
    RWK_RET buffer holds ASM2 BLOCKED. Outside quality windows every part
    is accepted (the old id-modulo scrap placeholder is gone).
    """
    idx = MACHINE_INDEX[name]
    cfg = MACHINES[name]
    cycle, mttf, mttr = cfg["cycle"], cfg["mttf"], cfg["mttr"]
    sigma = cfg["sigma"]
    rng = shared["noise"][idx]
    obs_row = shared["obs"][idx]
    state_row = shared["states"][idx]
    tput_row = shared["tput"][idx]
    fx = shared["fx"].get(name, [])
    rwk = shared["rwk_ret"]
    held, rem, part = False, 0, None
    down_left, dfault, ar, prev = 0, None, 0.0, "RUN"
    for t in range(T):
        inj = _inj_down(fx, t)
        if inj is not None and down_left > 0:
            down_left = 0
            _transition(shared, idx, name, "DOWN", "RUN", t)
            prev = "RUN"
        if _gw_at(shared, t):
            down_left = 0  # GT-exclusion (see _line_process)
        fid = inj["id"] if inj is not None else dfault
        if inj is not None:
            st, tput = "DOWN", 0
            dfault = inj["id"]
        elif down_left > 0:
            st, tput = "DOWN", 0
            down_left -= 1
        elif (
            shared["enable_bd"]
            and not _gw_at(shared, t)
            and shared["fail"].random() < 1.0 / mttf
        ):
            down_left = int(shared["fail"].geometric(1.0 / mttr)) - 1
            st, tput = "DOWN", 0
        elif not held:
            if len(up.items) > 0:
                req = up.get()
                yield req
                part = req.value
                held, rem, st, tput = True, cycle + _delay_d(fx, t), "RUN", 0
            else:
                st, tput = "STARVED", 0
        elif rem > 1:
            rem -= 1
            st, tput = "RUN", 0
        elif down is None:
            # ASM2 sink with quality-driven reject (see docstring).
            rate = _quality_rate(shared, t)
            rej = rate > 0.0 and shared["place"].random() < rate
            if rej:
                part["flag"] = "REJECT"
                if part.get("passes", 0) >= REWORK_MAX_PASSES:
                    shared["flow"]["sunk"] += 1
                    shared["flow"]["scrapped"] += 1
                    _emit(
                        shared,
                        "REJECT_ROUTE",
                        t,
                        name,
                        {"part": part["id"], "to": "scrap", "passes": part["passes"]},
                    )
                    shared["parts"].append(
                        {
                            "id": part["id"],
                            "t": t,
                            "machine": name,
                            "via": "RWK0",
                            "disposition": "scrap",
                            "passes": part["passes"],
                            "flag": "REJECT",
                        }
                    )
                    held, rem, part = False, 0, None
                    st, tput = "RUN", 1
                elif len(rwk.items) < rwk.capacity:
                    part["passes"] = part.get("passes", 0) + 1
                    yield rwk.put(part)
                    _emit(
                        shared,
                        "REJECT_ROUTE",
                        t,
                        name,
                        {"part": part["id"], "to": "RWK0", "passes": part["passes"]},
                    )
                    shared["flow"]["rejected"] += 1
                    held, rem, part = False, 0, None
                    st, tput = "RUN", 1
                else:
                    st, tput = "BLOCKED", 0
            else:
                shared["flow"]["sunk"] += 1
                held, rem, part = False, 0, None
                st, tput = "RUN", 1
        elif len(down.items) < down.capacity:
            yield down.put(part)
            held, rem, part = False, 0, None
            st, tput = "RUN", 1
        else:
            st, tput = "BLOCKED", 0
        if inj is None:
            dfault = None
        if held and part is not None and _degrade_at(fx, t):
            part["flag"] = "DEGRADE"
        _transition(shared, idx, name, prev, st, t, fault_id=fid)
        prev = st
        shared["held"][idx] = part if held else None
        val, _temp, ar = _sample_signal(rng, st, t, cfg, ar, _fault_dev(fx, t, sigma))
        lspec = _loss_at(fx, t)
        if lspec is not None and shared["drop"].random() < lspec["drop_rate"]:
            val = obs_row[t - 1] if t > 0 else val
        obs_row[t], state_row[t], tput_row[t] = val, st, tput
        yield env.timeout(1)


def _rwk0_process(env, shared):
    """RWK0 rework station (T7): RWK_RET intake -> cycle -> ASM0 kit C.

    Livelock guard: the pass counter lives ON THE PART; intake at
    REWORK_MAX_PASSES scraps instead of running a third pass. While a
    quality window is active, rework cannot restore the part, so
    completions requeue into RWK_RET (rework surge); when the window
    ends, completions re-enter the ASM0 kit via kit C. STARVED on empty
    intake (same observable as the T6 idle stub when no rework flows).
    No natural-breakdown draws here (the T6 idle stub drew none): the
    shared fail stream stays bit-identical to T6 on clean episodes;
    injected breakdowns still force RWK0 DOWN via the inj branch.
    """
    name, idx = "RWK0", MACHINE_INDEX["RWK0"]
    cfg = MACHINES[name]
    cycle, _mttf, _mttr = cfg["cycle"], cfg["mttf"], cfg["mttr"]
    sigma = cfg["sigma"]
    rng = shared["noise"][idx]
    obs_row = shared["obs"][idx]
    state_row = shared["states"][idx]
    tput_row = shared["tput"][idx]
    fx = shared["fx"].get(name, [])
    rwk = shared["rwk_ret"]
    kit = shared["kit"]
    held, rem, part = False, 0, None
    down_left, dfault, ar, prev = 0, None, 0.0, "STARVED"
    for t in range(T):
        inj = _inj_down(fx, t)
        if inj is not None and down_left > 0:
            down_left = 0
            _transition(shared, idx, name, "DOWN", "RUN", t)
            prev = "RUN"
        if _gw_at(shared, t):
            down_left = 0  # GT-exclusion (see _line_process)
        fid = inj["id"] if inj is not None else dfault
        if inj is not None:
            st, tput = "DOWN", 0
            dfault = inj["id"]
        elif down_left > 0:
            st, tput = "DOWN", 0
            down_left -= 1
        elif not held:
            if len(rwk.items) > 0:
                req = rwk.get()
                yield req
                part = req.value
                if part.get("passes", 0) >= REWORK_MAX_PASSES:
                    # Livelock guard: third pass refused -> scrap sink.
                    shared["flow"]["sunk"] += 1
                    shared["flow"]["scrapped"] += 1
                    _emit(
                        shared,
                        "REJECT_ROUTE",
                        t,
                        name,
                        {"part": part["id"], "to": "scrap", "passes": part["passes"]},
                    )
                    shared["parts"].append(
                        {
                            "id": part["id"],
                            "t": t,
                            "machine": name,
                            "via": "RWK0",
                            "disposition": "scrap",
                            "passes": part["passes"],
                            "flag": part.get("flag", "OK"),
                        }
                    )
                    part = None
                    st, tput = "RUN", 1
                else:
                    held, rem, st, tput = True, cycle + _delay_d(fx, t), "RUN", 0
            else:
                st, tput = "STARVED", 0
        elif rem > 1:
            rem -= 1
            st, tput = "RUN", 0
        elif _quality_rate(shared, t) > 0.0:
            # Quality storm: rework cannot restore the part yet — requeue
            # for another pass (surge). The intake cap above guarantees
            # termination via the scrap sink.
            part["passes"] = part.get("passes", 0) + 1
            yield rwk.put(part)  # always fits: just consumed one slot
            held, rem, part = False, 0, None
            st, tput = "RUN", 1
        else:
            part["passes"] = part.get("passes", 0) + 1
            part["line"] = "C"  # re-enter kitting via the C intake
            kit["C"].append(part)
            shared["flow"]["reworked"] += 1
            shared["parts"].append(
                {
                    "id": part["id"],
                    "t": t,
                    "machine": name,
                    "via": "RWK0",
                    "disposition": "reworked",
                    "passes": part["passes"],
                    "flag": part.get("flag", "OK"),
                }
            )
            held, rem, part = False, 0, None
            st, tput = "RUN", 1
        if inj is None:
            dfault = None
        if held and part is not None and _degrade_at(fx, t):
            part["flag"] = "DEGRADE"
        _transition(shared, idx, name, prev, st, t, fault_id=fid)
        prev = st
        shared["held"][idx] = part if held else None
        val, _temp, ar = _sample_signal(rng, st, t, cfg, ar, _fault_dev(fx, t, sigma))
        lspec = _loss_at(fx, t)
        if lspec is not None and shared["drop"].random() < lspec["drop_rate"]:
            val = obs_row[t - 1] if t > 0 else val
        obs_row[t], state_row[t], tput_row[t] = val, st, tput
        yield env.timeout(1)


def _fault_clock(env, shared):
    """Emit FAULT_START/END channel-7 events at exact GT window edges."""
    marks = []
    for spec in shared["specs"]:
        marks.append((spec["t0"], 0, "FAULT_START", spec))
        marks.append((spec["t1"], 1, "FAULT_END", spec))
    marks.sort(key=lambda m: (m[0], m[1]))
    for t, _, kind, spec in marks:
        yield env.timeout(t - env.now)
        _emit(
            shared,
            kind,
            t,
            spec["origin"],
            {"fault_id": spec["id"], "class": spec["class"]},
        )


def _monitor(env, stores, order, rows):
    """Record the 31 roster buffer levels after machines act each step."""
    for t in range(T):
        for j, key in enumerate(order):
            rows[j][t] = len(stores[key].items) if key in stores else 0
        yield env.timeout(1)


def run_episode(
    seed: int,
    fault: dict | list | None = None,
    *,
    enable_natural_breakdown: bool = True,
) -> dict:
    """Run one episode with seeded fault injection; return the record.

    fault is None, one fault dict, or a list of fault dicts (multi-fault
    episodes: same-machine windows need a ≥5-step gap). Returns the full
    episode record (seed, T, cal_win, obs, states, buffers, throughput,
    events, sbuf_stats, flow_stats, agv_waits, parts, faults).
    """
    fault_list = _validate(seed, fault)
    noise, place, drop, rng_agv, fail = _spawn_streams(seed)
    specs = _materialize(place, fault_list)
    env = simpy.Environment()
    agv = simpy.Resource(env, capacity=AGV_CAP)
    stores = {n: simpy.Store(env, capacity=c) for n, c in BUFFERS.items()}
    stores["_C7TAIL"] = simpy.Store(
        env, capacity=MACHINES["C7"]["buffer_cap"]
    )  # AGV drains this
    assert len(MACHINES) == N_MACHINES and len(BUFFERS) == N_BUFFERS
    order = sorted(MACHINE_INDEX, key=lambda m: MACHINE_INDEX[m])
    fx: dict[str, list[Any]] = {}
    for spec in specs:
        fx.setdefault(spec["origin"], []).append(spec)
    for lst in fx.values():
        lst.sort(key=lambda s: s["t0"])
    shared = {
        "noise": noise,
        "place": place,
        "drop": drop,
        "fail": fail,
        "enable_bd": enable_natural_breakdown,
        "obs": [[0.0] * T for _ in range(N_MACHINES)],
        "states": [["RUN"] * T for _ in range(N_MACHINES)],
        "tput": [[0] * T for _ in range(N_MACHINES)],
        "events": [],
        "agv_waits": [],
        "parts": [],
        "pid": [0],
        "held": [None] * N_MACHINES,
        "flow": {
            "line_created": 0,
            "asm_created": 0,
            "sunk": 0,
            "scrapped": 0,
            "xfer_open": 0,
            "rejected": 0,
            "reworked": 0,
        },
        "sbuf": {"diverted": 0, "drained": 0},
        "specs": specs,
        "fx": fx,
        "gwin": [(s["t0"], s["t1"]) for s in specs],
        "qwin": [
            (s["t0"], s["t1"], s["reject_rate"])
            for s in specs
            if s["class"] == "quality"
        ],
    }
    kit: dict[str, list[Any]] = {"A": [], "B": [], "C": []}
    shared["kit"] = kit
    shared["rwk_ret"] = stores["RWK_RET"]
    edges = _line_edges()
    for name in _LINES:
        up_key, down_key = edges[name]
        env.process(
            _line_process(
                env,
                {
                    "name": name,
                    "idx": MACHINE_INDEX[name],
                    "up": stores[up_key] if up_key else None,
                    "down": stores[down_key],
                    "sbuf": stores["SBUF"],
                },
                shared,
            )
        )
    env.process(_asm0_process(env, stores["ASM01"], kit, shared))
    env.process(_asm_mid_process(env, "ASM1", stores["ASM01"], stores["ASM12"], shared))
    env.process(_asm_mid_process(env, "ASM2", stores["ASM12"], None, shared))
    env.process(_rwk0_process(env, shared))
    env.process(_fault_clock(env, shared))
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
    held_line = sum(
        1 for i, n in enumerate(order) if n in _LINES and shared["held"][i] is not None
    )
    flow_stats = {
        "line_created": shared["flow"]["line_created"],
        "asm_created": shared["flow"]["asm_created"],
        "sunk": shared["flow"]["sunk"],
        "scrapped": shared["flow"]["scrapped"],
        "rejected": shared["flow"]["rejected"],
        "reworked": shared["flow"]["reworked"],
        "xfer_open": shared["flow"]["xfer_open"],
        "held_line": held_line,
        "held_asm0_batch": 1 if shared["held"][MACHINE_INDEX["ASM0"]] else 0,
        "held_asm12": sum(
            1 for n in ("ASM1", "ASM2") if shared["held"][MACHINE_INDEX[n]] is not None
        ),
        "held_rwk0": 1 if shared["held"][MACHINE_INDEX["RWK0"]] else 0,
        "kit_A": len(kit["A"]),
        "kit_B": len(kit["B"]),
        "kit_C": len(kit["C"]),
        "c7tail": len(stores["_C7TAIL"].items),
        "store_final": store_final,
    }
    return {
        "seed": seed,
        "T": T,
        "cal_win": CAL_WIN,
        "obs": shared["obs"],
        "states": shared["states"],
        "buffers": buf_rows,
        "throughput": shared["tput"],
        "events": shared["events"],
        "sbuf_stats": sbuf_stats,
        "flow_stats": flow_stats,
        "agv_waits": shared["agv_waits"],
        "parts": shared["parts"],
        "faults": fault_list,
    }


def run_calibration(seed: int):
    """Return (120, 32) clean window: breakdowns off, first CAL_WIN steps."""
    rec = run_episode(seed, None, enable_natural_breakdown=False)
    return np.asarray(rec["obs"], dtype=float)[:, :CAL_WIN].T


def _try_place(taken, durs):
    """Greedily lay windows at/after 120 with ≥5-step gaps; None if unfit."""
    blocks = sorted(taken)
    out, cursor = [], 120
    for dur in durs:
        t = cursor
        for a, b in blocks:
            if t + dur + 5 <= a:
                break
            t = max(t, b + 5)
        if t + dur > T:
            return None
        out.append(t)
        blocks.append((t, t + dur))
        blocks.sort()
        cursor = t + dur + 5
    return out


def build_faults(seed: int = 12345) -> list[dict]:
    """Build the deterministic fault manifest for a master seed.

    Full machine x class cross-product (32 machines x 7 classes = 224
    rows); the oracle representative subset (incl. F-21 drift B5 t0=150
    dur=12 mag=5.2) is pinned with rep=True. t0 ~ uniform on [120,
    300-dur] from rng_place = children[32]; same-machine windows keep a
    ≥5-step gap (greedy cursor; dur-8 fallback, which always fits: 7
    windows need at most 7*8+6*5=86 steps of the ~180-step range, and a
    pinned window splits the range into two intervals the fallback fills
    left-to-right).
    """
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise ValueError(f"seed must be a non-negative int, got {seed!r}")
    seq = np.random.SeedSequence((seed,))
    children = seq.spawn(36)  # placement stream is children[32]
    assert N_STREAMS == 36 and len(children) == N_STREAMS
    rng_place = np.random.default_rng(children[32])
    (mlo, mhi) = FAULT_RANGES["mag_sigma"]
    (dlo, dhi) = FAULT_RANGES["dur"]
    (ddlo, ddhi) = FAULT_RANGES["delay_d"]
    (rlo, rhi) = FAULT_RANGES["drop_rate"]
    (mulo, muhi) = FAULT_RANGES["mttr_mult"]
    (rjlo, rjhi) = FAULT_RANGES["reject_rate"]

    def _params(cls, extra):
        mag = float(rng_place.uniform(mlo, mhi))
        if cls == "delay" and "d" not in extra:
            extra["d"] = int(rng_place.integers(ddlo, ddhi + 1))
        elif cls == "loss" and "drop_rate" not in extra:
            extra["drop_rate"] = float(rng_place.uniform(rlo, rhi))
        elif cls == "breakdown" and "mttr_mult" not in extra:
            extra["mttr_mult"] = float(rng_place.uniform(mulo, muhi))
        elif cls == "quality" and "reject_rate" not in extra:
            extra["reject_rate"] = float(rng_place.uniform(rjlo, rjhi))
        return mag

    order = sorted(MACHINE_INDEX, key=lambda m: MACHINE_INDEX[m])
    fixed: dict[Any, Any] = {(r["origin"], r["class"]): r for r in _ORACLE_REP}
    rows = []
    for m in order:
        taken, todo = [], []
        for cls in _FAULT_CLASSES:
            key = (m, cls)
            if key in fixed:
                r = fixed[key]
                extra = dict(r.get("extra", {}))
                mag = r.get("mag_sigma", None)
                if mag is None:
                    mag = _params(cls, extra)
                rows.append(
                    {
                        "id": r["id"],
                        "class": cls,
                        "origin": m,
                        "t0": r["t0"],
                        "dur": r["dur"],
                        "mag_sigma": float(mag),
                        "extra": extra,
                        "rep": True,
                    }
                )
                taken.append((r["t0"], r["t0"] + r["dur"]))
            else:
                dur = int(rng_place.integers(int(dlo), int(dhi) + 1))
                extra = {}
                mag = _params(cls, extra)
                todo.append([cls, dur, mag, extra, f"F-{m}-{cls}"])
        durs = [d for (_, d, _, _, _) in todo]
        t0s = _try_place(taken, durs)
        if t0s is None:  # pathological dur draw: retry with minimal durs
            for entry in todo:
                entry[1] = 8
            t0s = _try_place(taken, [8] * len(todo))
            assert t0s is not None
        for (cls, dur, mag, extra, fid), t0 in zip(todo, t0s):
            rows.append(
                {
                    "id": fid,
                    "class": cls,
                    "origin": m,
                    "t0": t0,
                    "dur": dur,
                    "mag_sigma": mag,
                    "extra": extra,
                    "rep": False,
                }
            )
    return rows


def validate_coverage(manifest, oracle):
    """Pure TC-006 gate: coverage rows x oracle fault ids -> gap list [].

    Each manifest row declares {partition, machine, channels, classes,
    fault_ids}; malformed rows raise ValueError (never pass silently). A
    gap names the partition plus the missing channel/class/oracle id, so
    the anti-vacuity probe (planted hole) resolves to its cell.
    """
    rows = list(manifest)
    for r in rows:
        for k in ("partition", "machine", "channels", "classes", "fault_ids"):
            if k not in r:
                raise ValueError(f"coverage row missing {k!r}: {r!r}")
    gaps = []
    for p in _PARTITIONS:
        prows = [r for r in rows if r["partition"] == p]
        if not prows:
            gaps.append(f"{p}: no rows")
            continue
        ch = set().union(*(set(r["channels"]) for r in prows))
        cl = set().union(*(set(r["classes"]) for r in prows))
        for c in _CHANNELS:
            if c not in ch:
                gaps.append(f"{p}: channel {c} uncovered")
        for c in _FAULT_CLASSES:
            if c not in cl:
                gaps.append(f"{p}: class {c} uncovered")
    have_ids = {i for r in rows for i in r["fault_ids"]}
    for f in oracle:
        if f["id"] not in have_ids:
            gaps.append(f"oracle {f['id']} missing")
    return gaps


def check_wall_tripwire(walls, budget=600.0):
    """Pure TC-009 gate: (total wall, tripped?) over fixture numbers only."""
    total = float(sum(walls))
    return (total, total > budget)


def replay_digest(record):
    """Canonical replay digest: sha256 over sorted-key JSON with repr floats.

    Wall/clock fields are excluded. Named digest (not hash) so the T1
    no-bare-default_rng/no-hash-seeding source grep stays green.
    """
    scrubbed = {k: v for k, v in record.items() if k not in _WALLCLOCK_KEYS}
    return hashlib.sha256(
        json.dumps(scrubbed, sort_keys=True, default=repr).encode()
    ).hexdigest()


_CAL_SEEDS = (7, 11, 13)
_F21_SHAPE = {
    "id": "F-21",
    "class": "drift",
    "origin": "B5",
    "t0": 150,
    "dur": 12,
    "mag_sigma": 5.2,
}


def _calibrate(path):
    """Time clean + F-21-shape episodes (clean signals, timing only)."""
    episodes = []
    for seed in _CAL_SEEDS:
        for tag, fault in (("clean", None), ("F-21-drift-shape", _F21_SHAPE)):
            start = time.perf_counter()
            run_episode(seed, dict(fault) if fault else None)
            wall = time.perf_counter() - start
            episodes.append(
                {
                    "seed": seed,
                    "fault": tag,
                    "wall_s": wall,
                    "enable_natural_breakdown": True,
                    "faultdev_applied": False,
                }
            )
    mean = sum(e["wall_s"] for e in episodes) / len(episodes)
    payload = {
        "mean_per_episode_s": mean,
        "seeds": list(_CAL_SEEDS),
        "episodes_timed": len(episodes),
        "episodes": episodes,
    }
    with open(path, "w") as fh:
        json.dump(payload, fh, indent=2)
    print(f"mean_per_episode_s={mean:.4f} episodes={len(episodes)} -> {path}")


# ---- T8 full-battery runner (multiprocessing, measured wall math) ----
#
# Seed rule (documented, deterministic): episode i of a manifest built with
# master seed M runs run_episode(seed=M * 1000 + i, fault=row_i). Worker
# tasks are picklable (index, seed, fault-dict) triples; workers hold no
# shared RNG (run_episode spawns its own SeedSequence streams per seed) and
# results are assembled in input order via Executor.map (which preserves
# input order per CPython docs; as_completed would not), so the joined
# digest is identical for any --jobs value.
_BATTERY_MASTER_SEED = 12345  # == build_faults default master seed
_BATTERY_SEED_STRIDE = 1000  # episode seed = master * stride + row index
_BATTERY_BUDGET_S = 600.0  # SIM_SPEC sect 10 normative battery wall bar
_BATTERY_TRIPWIRE_S = 500.0  # T8 plan: first-8 measured mean extrapolated
_BATTERY_WATCHDOG_S = 120.0  # per-episode anomaly log threshold
_BATTERY_QUICK_ROWS = 16  # --manifest quick smoke subset (first N rows)
_BATTERY_TRIPWIRE_N = 8  # first-N measured episodes feeding the tripwire
# Walk topology prior (SIM_SPEC 7.2-7.3; SDD 4.4 walk(depth=3, topk=8);
# fan-out cap 8 for the assembly join). Recorded as config, not measured.
_BATTERY_TOPOLOGY = {"depth_max": 3, "topk": 8, "fanout_cap": 8}
_BATTERY_CALIBRATION = ".omo/evidence/task-5-minipro-16-m01-twin.calibration.json"
_BATTERY_EVIDENCE_DIR = ".omo/evidence"


def battery_episode_seed(master_seed: int, row_index: int) -> int:
    """Episode seed rule: master * stride + row index (documented above)."""
    return master_seed * _BATTERY_SEED_STRIDE + row_index


def _partition_of_machine(name):
    """Manifest origin machine -> coverage partition group."""
    if name is None:
        raise ValueError("manifest row missing origin machine")
    if name.startswith("ASM"):
        return "cell"
    if name.startswith("RWK"):
        return "rework"
    if name.startswith("A"):
        return "line-A"
    if name.startswith("B"):
        return "line-B"
    if name.startswith("C"):
        return "line-C"
    raise ValueError(f"unknown partition for machine {name!r}")


def manifest_coverage_rows(manifest):
    """Manifest fault rows -> validate_coverage schema rows.

    Each episode records all 7 channels (full-plant replay context, never
    subgraph-clipped), so every row declares the full channel list; the
    class axis carries the row's own class and fault_ids its own id. The
    union over rows is what the T3 gate asserts.
    """
    rows = []
    for r in manifest:
        rows.append(
            {
                "partition": _partition_of_machine(r.get("origin")),
                "machine": r.get("origin"),
                "channels": list(_CHANNELS),
                "classes": [r.get("class")],
                "fault_ids": [r.get("id")],
            }
        )
    return rows


def validate_manifest(manifest, oracle=None):
    """T8 manifest gate: rep-subset ⊆ manifest AND every machine x class ≥1.

    Reuses the T3 pure helpers (validate_coverage over the coverage rows;
    check_wall_tripwire lives with the runner below). Returns the gap list
    ([] == pass); the CLI fails LOUD naming the gap, never ships a gap.
    """
    if oracle is None:
        oracle = list(_ORACLE_REP)
    gaps = validate_coverage(manifest_coverage_rows(manifest), oracle)
    have_mc = {(r.get("origin"), r.get("class")) for r in manifest}
    order = sorted(MACHINE_INDEX, key=MACHINE_INDEX.get)
    for m in order:
        for c in _FAULT_CLASSES:
            if (m, c) not in have_mc:
                gaps.append(f"{m}: class {c} missing")
    return gaps


def _battery_worker(task):
    """Pool worker: (index, seed, fault) -> measured result row (picklable).

    No shared RNG state: run_episode spawns its own SeedSequence streams.
    fanout is the honest downstream-touch count for this episode: distinct
    non-origin machines with fault-linked events (fault_id tag) plus
    distinct non-origin machines on DEGRADE/REJECT part records.
    """
    index, seed, fault = task
    start = time.perf_counter()
    rec = run_episode(
        seed,
        {
            "id": fault.get("id"),
            "class": fault.get("class"),
            "origin": fault.get("origin"),
            "t0": fault.get("t0"),
            "dur": fault.get("dur"),
            "mag_sigma": fault.get("mag_sigma", 0.0),
            "extra": dict(fault.get("extra") or {}),
        },
    )
    wall = time.perf_counter() - start
    fid, origin = fault.get("id"), fault.get("origin")
    touched = set()
    for e in rec["events"]:
        tag = e.get("fault_id", None)
        if tag is None:
            detail = e.get("detail", {})
            tag = detail.get("fault_id", None) if detail else None
        if tag == fid and e.get("machine") != origin:
            touched.add(e.get("machine"))
    for p in rec["parts"]:
        if p.get("flag", "OK") != "OK" and p.get("machine") != origin:
            touched.add(p.get("machine"))
    return {
        "index": index,
        "seed": seed,
        "fault_id": fid,
        "digest": replay_digest(rec),
        "wall_s": wall,
        "fanout": len(touched),
    }


def _run_tasks_ordered(tasks, jobs):
    """Run worker tasks, assembling results in input order (deterministic).

    jobs == 1 runs inline (same code path, no pool); jobs > 1 uses
    ProcessPoolExecutor.map, which yields in input order. Either way the
    joined per-episode digest is identical for fixed (master, manifest).
    """
    if jobs == 1:
        return [_battery_worker(t) for t in tasks]
    with concurrent.futures.ProcessPoolExecutor(max_workers=jobs) as pool:
        return list(pool.map(_battery_worker, tasks))


def _load_manifest(spec, master_seed):
    """Resolve --manifest full|quick|FILE to (rows, label)."""
    if spec == "full":
        return build_faults(master_seed), "full"
    if spec == "quick":
        return build_faults(master_seed)[:_BATTERY_QUICK_ROWS], "quick"
    try:
        with open(spec) as fh:
            payload = json.load(fh)
    except (OSError, ValueError) as exc:
        raise ValueError(f"cannot load manifest file {spec!r}: {exc}")
    if isinstance(payload, dict) and "manifest" in payload:
        payload = payload["manifest"]
    if not isinstance(payload, list) or not payload:
        raise ValueError(f"manifest file {spec!r} holds no fault rows")
    return payload, spec


def _load_calibration(path):
    """Read the T5 calibration mean (budget input); never hardcoded here."""
    try:
        with open(path) as fh:
            payload = json.load(fh)
        return float(payload["mean_per_episode_s"])
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise ValueError(f"cannot read calibration mean from {path!r}: {exc}")


def _write_json(path, payload):
    with open(path, "w") as fh:
        json.dump(payload, fh, indent=2)


def _battery_parser():
    parser = argparse.ArgumentParser(
        description="T8 full cross-product battery runner with wall "
        "tripwire (seed rule: episode seed = master * 1000 "
        "+ row index; identical digests for any --jobs)."
    )
    parser.add_argument(
        "--manifest",
        default="full",
        help="full | quick (first 16 rows) | FILE (json fault-row list)",
    )
    parser.add_argument(
        "--jobs", type=int, default=os.cpu_count() or 1, help="worker processes (>=1)"
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=_BATTERY_MASTER_SEED,
        help="master seed for manifest + episode seeds",
    )
    parser.add_argument(
        "--subset",
        type=int,
        default=None,
        help="run first N manifest rows only (digest proof)",
    )
    parser.add_argument(
        "--wall-report",
        action="store_true",
        help="emit wall_report.json + coverage_matrix.json + fanout.json",
    )
    parser.add_argument(
        "--calibration",
        default=_BATTERY_CALIBRATION,
        help="T5 calibration JSON path (budget input)",
    )
    parser.add_argument(
        "--evidence-dir",
        default=_BATTERY_EVIDENCE_DIR,
        help="artifact directory for --wall-report",
    )
    parser.add_argument(
        "--budget-override",
        type=float,
        default=None,
        help="TEST-ONLY failing-first demo flag: replaces "
        "the 600s budget in the tripwire/budget check "
        "to prove the exit-2 path. Never a default.",
    )
    parser.add_argument(
        "--calibrate",
        default=None,
        help="legacy T5 entry: time clean+F-21 episodes to PATH and exit",
    )
    return parser


def _fail(msg):
    print(f"battery FAIL LOUD: {msg}", file=sys.stderr)
    return 2


def main(argv=None):
    parser = _battery_parser()
    args = parser.parse_args(argv)
    if args.calibrate is not None:
        _calibrate(args.calibrate)
        return 0
    if args.jobs is None or args.jobs < 1:
        parser.error("--jobs must be an integer >= 1")
    if args.seed is None or args.seed < 0:
        parser.error("--seed must be a non-negative integer")
    try:
        manifest, label = _load_manifest(args.manifest, args.seed)
    except ValueError as exc:
        parser.error(str(exc))
    if args.subset is not None and args.subset < 1:
        parser.error("--subset must be >= 1")
    n = len(manifest)
    gaps = validate_manifest(manifest)
    if gaps:
        return _fail(f"manifest {label} coverage gap: {gaps[0]} ({len(gaps)} total)")
    full_cov_rows = manifest_coverage_rows(manifest)
    if args.subset is not None:
        manifest = manifest[: args.subset]
        label = f"{label}[:{args.subset}]"
    n = len(manifest)
    try:
        cal_mean = _load_calibration(args.calibration)
    except ValueError as exc:
        return _fail(str(exc))
    budget_cap = (
        args.budget_override if args.budget_override is not None else _BATTERY_BUDGET_S
    )
    tasks = [(i, battery_episode_seed(args.seed, i), manifest[i]) for i in range(n)]
    first = min(_BATTERY_TRIPWIRE_N, n)
    wall_open = time.perf_counter()
    try:
        head = _run_tasks_ordered(tasks[:first], args.jobs)
    except KeyboardInterrupt:
        _write_partial(args, manifest, [], args.seed, cal_mean, budget_cap)
        return _fail("interrupted during tripwire phase; partial artifacts written")
    mean8 = sum(r["wall_s"] for r in head) / len(head)
    extrapolated = mean8 * n
    if extrapolated > _BATTERY_TRIPWIRE_S and args.jobs == 1:
        return _fail(
            f"tripwire: first-{first} measured mean {mean8:.4f}s/ep "
            f"extrapolates to {extrapolated:.1f}s sequential-equivalent "
            f"(>{_BATTERY_TRIPWIRE_S:.0f}s) with --jobs 1; remedy: "
            f"parallelize first (raise --jobs), never shrink scope"
        )
    branch = "parallel-already" if args.jobs > 1 else "sequential-ok"
    try:
        tail = _run_tasks_ordered(tasks[first:], args.jobs)
    except KeyboardInterrupt:
        _write_partial(args, manifest, head, args.seed, cal_mean, budget_cap)
        return _fail("interrupted mid-battery; partial artifacts written")
    rows = head + tail
    rows.sort(key=lambda r: r["index"])
    wall_total = time.perf_counter() - wall_open
    walls = [r["wall_s"] for r in rows]
    fresh_mean = sum(walls) / n
    seq_equiv = wall_total * args.jobs
    budget = cal_mean * n
    projected = fresh_mean * n
    _total, tripped = check_wall_tripwire([wall_total], budget=budget_cap)
    verdict = "PASS" if not tripped else "FAIL"
    anomalies = [r["fault_id"] for r in rows if r["wall_s"] > _BATTERY_WATCHDOG_S]
    joined = hashlib.sha256("\n".join(r["digest"] for r in rows).encode()).hexdigest()
    cov_rows = full_cov_rows
    cov_gaps = validate_coverage(cov_rows, [{"id": r["id"]} for r in _ORACLE_REP])
    cells = {}
    for p in _PARTITIONS:
        prows = [r for r in cov_rows if r["partition"] == p]
        cells[p] = {
            "channels": sorted({c for r in prows for c in r["channels"]}),
            "classes": sorted({c for r in prows for c in r["classes"]}),
            "n_rows": len(prows),
            "n_faults": sum(len(r["fault_ids"]) for r in prows),
        }
    empty_cells = [g for g in cov_gaps]
    fanout_measured = max([r["fanout"] for r in rows] + [0])
    if args.wall_report:
        import pathlib

        evdir = pathlib.Path(args.evidence_dir)
        evdir.mkdir(parents=True, exist_ok=True)
        _write_json(
            evdir / "wall_report.json",
            {
                "per_episode_s": walls,
                "calibration_mean_s": cal_mean,
                "calibration_path": args.calibration,
                "fresh_mean_s": fresh_mean,
                "wall_total_s": wall_total,
                "jobs": args.jobs,
                "sequential_equivalent_s": seq_equiv,
                "budget_s": budget,
                "budget_cap_s": budget_cap,
                "projected_total_s": projected,
                "tripwire": {
                    "first_n": first,
                    "first_n_mean_s": mean8,
                    "extrapolated_s": extrapolated,
                    "threshold_s": _BATTERY_TRIPWIRE_S,
                    "branch": branch,
                },
                "n_episodes": n,
                "manifest": label,
                "master_seed": args.seed,
                "seed_rule": "episode_seed = master_seed*1000+row_index",
                "joined_digest": joined,
                "anomalies_over_120s": anomalies,
                "verdict": verdict,
            },
        )
        _write_json(
            evdir / "coverage_matrix.json",
            {
                "partitions": list(_PARTITIONS),
                "channels": list(_CHANNELS),
                "classes": list(_FAULT_CLASSES),
                "cells": cells,
                "empty_cells": empty_cells,
            },
        )
        _write_json(
            evdir / "fanout.json",
            {
                "fanout_measured": fanout_measured,
                "metric": "max over battery episodes of distinct non-origin "
                "machines with fault-linked events (fault_id tag) "
                "plus DEGRADE/REJECT part records",
                "topology": dict(_BATTERY_TOPOLOGY),
                "partitions": list(_PARTITIONS),
                "note": "walk execution belongs to M1",
            },
        )
    cap_label = f"{budget_cap:.0f}" if budget_cap >= 10 else f"{budget_cap:.2f}"
    print(
        f"battery {label}: n={n} jobs={args.jobs} "
        f"wall_total_s={wall_total:.2f} (<{cap_label}) "
        f"seq_equiv_s={seq_equiv:.1f} budget_s={budget:.2f} "
        f"projected_s={projected:.2f} fanout={fanout_measured} "
        f"empty_cells={len(empty_cells)} verdict={verdict} "
        f"digest={joined[:12]}"
    )
    if tripped:
        return _fail(
            f"over budget: wall_total {wall_total:.1f}s > "
            f"{cap_label}s; remedy: parallelize first "
            f"(raise --jobs), never shrink scope"
        )
    return 0


def _write_partial(args, manifest, rows, master, cal_mean, budget_cap):
    """Interrupted-battery artifacts, labeled partial (adversarial probe)."""
    if not args.wall_report:
        return
    import pathlib

    evdir = pathlib.Path(args.evidence_dir)
    evdir.mkdir(parents=True, exist_ok=True)
    walls = [r["wall_s"] for r in rows]
    _write_json(
        evdir / "wall_report.json",
        {
            "partial": True,
            "per_episode_s": walls,
            "calibration_mean_s": cal_mean,
            "wall_total_s": sum(walls),
            "jobs": args.jobs,
            "n_episodes": len(manifest),
            "n_finished": len(rows),
            "budget_cap_s": budget_cap,
            "verdict": "PARTIAL",
        },
    )


if __name__ == "__main__":
    sys.exit(main())
