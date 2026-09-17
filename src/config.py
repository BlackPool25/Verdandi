"""Twin-only constants — SIM_SPEC Table 3.1 + twin scalars (T4).

Twin subset ONLY: per-machine operating points, buffers, AGV/SBUF, fault
ranges, state offsets. No detector/walk/PCMCI/narration constants live here
(downstream milestones own them). src/twin.py MUST import these, never
hardcode the same value twice (TECHNICAL.md config table).

Machine entry keys: class, base, sigma, cycle (cycle_steps), mttf, mttr,
buffer_cap (buffer after machine; None = sink + rework tap), transit
(nominal transit steps to next; None = sink).
"""

import math
from typing import Any

# Episode / calibration scalars (SIM_SPEC Table 3.1 header + §2.3).
T = 300
CAL_WIN = 120
N_MACHINES = 26
N_BUFFERS = 26
N_STREAMS = 36

# Topology-A schema version (MINIPRO-33): v2 = 26-machine roster. v1
# 32-machine baselines are V1_NON_COMPARABLE, never asserted equal.
# MINIPRO-34 Todo 1: v3 adds five 26x300 physics grids (therm/wear/force/
# inrush/life) + the couplings active-flags snapshot. v2 digests are
# V2_NON_COMPARABLE, never asserted equal.
TWIN_SCHEMA = 3
CODE_VERSION = "twin-3.0.0-xcouplings"

# INSP0 holds each part exactly this many steps before late-verdict release.
INSPECT_DELAY_STEPS = 3

# Shared resources (SIM_SPEC §2.2).
# Owner-approved option C (bounded MINIPRO-24 retime, 2026-09-17): AGV_CAP
# 2->3. Rationale: AGV drain throttles the C-line kit feed (C7 BLOCKED 45
# steps/episode at cap 2, kit_C=0 vs kit_A=19/kit_B=18 backlog); in-memory
# probe measured +5-6pp RUN with balanced-kit signature. Cap 3 keeps the
# 2-queue gate shape (AGV_CAP+2) and the hold distribution unchanged.
AGV_CAP = 3
AGV_STEPS = (4, 8)  # ints: uniform transit per trip, sampled on rng_agv stream
SBUF_CAP = 30
# Owner-approved option C: land-grace bound for AGV drain accounting. An
# xfer spawned at t_req lands at t_req+queue_wait+hold; the drain phase
# runs the (already obs-silent) AGV processes until T+AGV_DRAIN_GRACE so
# in-flight xfers land instead of leaking xfer_open. Bound = max hold (8):
# covers any zero-wait tail spawn; the spawn guard covers the rest.
AGV_DRAIN_GRACE = 8
# Owner-approved option C: standby-scope decision for duty_cycle().
# B7S (spare: ~1 failover/episode, idle by construction) and RWK0 (rework
# loop: zero flow on clean episodes, idle by design) are EXCLUDED from the
# plant duty mean. Rationale: counting redundancy/rework-by-design as
# starved punishes spare capacity, not flow health. Scope change recorded
# for SIM_SPEC Todo 10 (plant mean is now over 24 machines, not 26).
STANDBY_EXCLUDED = frozenset({"B7S", "RWK0"})
# Owner ruling 2026-09-12: process/finish divert, feed/form never; inspect
# tails excluded — A9/B9/C7 ride the AGV path, never SBUF-direct
# (guard `cfg["class"] in SBUF_DIVERT_CLASSES and name not in _TAILS`).
SBUF_DIVERT_CLASSES = frozenset({"process", "finish", "inspect-tail"})

# Rework loop (SIM_SPEC §2.1; TEST_CASES TC-006b max-passes cap).
REWORK_MAX_PASSES = 2

# Signal envelope: base ± 3σ on clean data (SIM_SPEC Table 3.1 notes, §7).
ENVELOPE_SIGMA = 3.0

# State offsets in units of σ (SIM_SPEC §4.1: STARVED −2σ, BLOCKED −1σ, DOWN −3σ).
STATE_OFFSETS = {"RUN": 0.0, "STARVED": -2.0, "BLOCKED": -1.0, "DOWN": -3.0}

# Fault injection ranges (SIM_SPEC §5): mag 4–7σ, dur 8–25, delay d∈[3,6],
# loss drop 10–30%, breakdown mttr_mult∈[1,3], quality reject 15–40%.
FAULT_RANGES = {
    "mag_sigma": (4.0, 7.0),
    "dur": (8, 25),
    "delay_d": (3, 6),
    "drop_rate": (0.10, 0.30),
    "mttr_mult": (1.0, 3.0),
    "reject_rate": (0.15, 0.40),
}

# Nominal temperature bands in °C (SIM_SPEC §8 channel 2): process 60–95,
# feed/form 20–45, assembly 25–55, test/rework 20–60. Finish rides the hot
# line band; inspect tails ride the test band (§8 has four bands only).
TEMP_RANGES = {
    "feed": (20.0, 45.0),
    "form": (20.0, 45.0),
    "process": (60.0, 95.0),
    "finish": (60.0, 95.0),
    "inspect-tail": (20.0, 60.0),
    "assembly-kit": (25.0, 55.0),
    "assembly-join": (25.0, 55.0),
    "test": (20.0, 60.0),
    "rework": (20.0, 60.0),
}

# A SIM "STUCK" event (part wedged, zero throughput at origin) classifies as
# the breakdown fault class: forced DOWN for the window (SIM_SPEC §5).
STUCK_IS_BREAKDOWN = {"STUCK": "breakdown"}


def _row(cls, base, sigma, cycle, mttf, mttr, buffer_cap, transit):
    return {
        "class": cls,
        "base": base,
        "sigma": sigma,
        "cycle": cycle,
        "mttf": mttf,
        "mttr": mttr,
        "buffer_cap": buffer_cap,
        "transit": transit,
    }


# Per-machine Table 3.1 rows: (name, entry). Topology-A roster (26):
# line survivors A0,A1,A2,A7,A8,A9 / B0,B1,B2,B8,B9 / C0,C1,C2,C6,C7
# (interiors A3-A6/B3-B6/C3-C5 dropped, single B7 removed) + B7P/B7S
# redundant pair + PKG0/PKG1/PKG2 packaging fork + INSP0 delay node
# + ASM0,ASM1,ASM2,RWK0 cell.
#
# Owner-approved option C TAKT5 retime (2026-09-17): single-takt line
# balancing at takt=5 (the form/kit cadence A1/B1/C1/ASM0/PKG0 already
# ran). Every consumer at-or-slower than its producer kills structural
# upstream-empty STARVED. Changed cycles old->new with reason:
# feed 4->5 (A0,B0,C0: match takt, stop overproduction/BLOCKED risk);
# process 6->5 (A2,A7,B2,B7P,C2,C6: feed the finish tier 1:1);
# finish 4->5 (A8,B8: match slowed producers, was ~1/3 idle);
# inspect-tail 3->5 (A9,B9,C7: match feeders; C7 AGV-drained);
# assembly-join 6->5 (ASM1), test 3->5 (ASM2: match kit cadence);
# finish-sink 4->10 (PKG1,PKG2: PKG0@5 round-robins, each tail fed 1/10).
# Frozen: A1/B1/C1 (already 5), PKG0/ASM0 (already 5), INSP0 (2:
# delay-paced via INSPECT_DELAY_STEPS, cycle knob is dead), B7S (6:
# spare, excluded from duty mean; pair asymmetry only in failover
# windows), RWK0 (8: rework loop, excluded from duty mean).
# Classes, mttf/mttr, buffer caps, transits, signal coefficients all frozen.
_MACHINE_ROWS = [
    ("A0", _row("feed", 50.0, 1.0, 5, 2000, 15, 20, 2)),
    ("A1", _row("form", 60.0, 1.2, 5, 1500, 12, 20, 2)),
    ("A2", _row("process", 70.0, 1.5, 5, 800, 20, 25, 3)),
    ("A7", _row("process", 70.0, 1.5, 5, 800, 20, 25, 3)),
    ("A8", _row("finish", 55.0, 1.1, 5, 1200, 10, 15, 3)),
    ("A9", _row("inspect-tail", 48.0, 1.4, 5, 1500, 8, 15, None)),
    ("B0", _row("feed", 50.0, 1.0, 5, 2000, 15, 20, 2)),
    ("B1", _row("form", 60.0, 1.2, 5, 1500, 12, 20, 2)),
    ("B2", _row("process", 70.0, 1.5, 5, 800, 20, 25, 3)),
    ("B7P", _row("process", 70.0, 1.5, 5, 800, 20, 25, 3)),
    ("B7S", _row("process", 70.0, 1.5, 6, 800, 20, 25, 3)),
    ("B8", _row("finish", 55.0, 1.1, 5, 1200, 10, 15, 3)),
    ("B9", _row("inspect-tail", 48.0, 1.4, 5, 1500, 8, 15, None)),
    ("C0", _row("feed", 50.0, 1.0, 5, 2000, 15, 20, 2)),
    ("C1", _row("form", 60.0, 1.2, 5, 1500, 12, 20, 2)),
    ("C2", _row("process", 70.0, 1.5, 5, 800, 20, 25, 3)),
    ("C6", _row("process", 70.0, 1.5, 5, 800, 20, 25, 3)),
    # C7 "finish" label is line shorthand only (Table 3.1 note); params are inspect.
    # buffer_cap=15 (tail cap governs dedicated _C7TAIL store); mttr=8 is repair, not cap.
    ("C7", _row("inspect-tail", 48.0, 1.4, 5, 1500, 8, 15, None)),
    ("PKG0", _row("assembly-kit", 65.0, 1.3, 5, 1000, 12, 25, 2)),
    ("PKG1", _row("finish", 55.0, 1.1, 10, 1200, 10, 15, None)),
    ("PKG2", _row("finish", 55.0, 1.1, 10, 1200, 10, 15, None)),
    # ASM0 cycle 5 explicit per Table 3.1 (assembly/kit).
    ("ASM0", _row("assembly-kit", 65.0, 1.3, 5, 1000, 12, 25, 2)),
    ("ASM1", _row("assembly-join", 66.0, 1.3, 5, 1000, 12, 25, 2)),
    ("INSP0", _row("test", 45.0, 2.0, 2, 1200, 10, 25, 2)),
    # ASM2 σ=2.0 kept noisy per spec — do not quiet it; VETO_ASM2 compensates (§7).
    ("ASM2", _row("test", 45.0, 2.0, 5, 1200, 10, None, None)),
    ("RWK0", _row("rework", 62.0, 1.6, 8, 900, 18, 10, 5)),
]

for _tail in ("A9", "B9", "C7"):
    for _name, _entry in _MACHINE_ROWS:
        if _name == _tail:
            _entry["transit"] = AGV_STEPS

MACHINES = dict(_MACHINE_ROWS)

# Canonical index order (topology-A literal, index = noise stream):
# A0:0,A1:1,A2:2,A7:3,A8:4,A9:5, B0:6,B1:7,B2:8,B7P:9,B7S:10,B8:11,B9:12,
# C0:13,C1:14,C2:15,C6:16,C7:17, PKG0:18,PKG1:19,PKG2:20,
# ASM0:21,ASM1:22,INSP0:23,ASM2:24,RWK0:25.
# Survivor moves (old->new): A7 7->3, A8 8->4, A9 9->5, B0 10->6,
# B1 11->7, B2 12->8, B8 18->11, B9 19->12, C0 20->13, C1 21->14,
# C2 22->15, C6 26->16, C7 27->17, ASM0 28->21, ASM1 29->22,
# ASM2 30->24, RWK0 31->25. Noise children 26-31 retired.
MACHINE_INDEX = {
    "A0": 0,
    "A1": 1,
    "A2": 2,
    "A7": 3,
    "A8": 4,
    "A9": 5,
    "B0": 6,
    "B1": 7,
    "B2": 8,
    "B7P": 9,
    "B7S": 10,
    "B8": 11,
    "B9": 12,
    "C0": 13,
    "C1": 14,
    "C2": 15,
    "C6": 16,
    "C7": 17,
    "PKG0": 18,
    "PKG1": 19,
    "PKG2": 20,
    "ASM0": 21,
    "ASM1": 22,
    "INSP0": 23,
    "ASM2": 24,
    "RWK0": 25,
}

# Buffer roster (26, SIM_SPEC §2.2 topology-A): 16 line-gap + 5 cell
# (ASM01, INSP01, INSP02, GA9, GB9) + 3 pkg (C7PKG, PKG01, PKG02)
# + RWK_RET + SBUF. Gap caps mirror the upstream machine's buffer cap;
# C7 tail stages in the dedicated cap-15 _C7TAIL store (AGV-drained,
# off-roster, never the C67 gap buffer).
_BUFFER_ROWS = [
    ("A01", 20),
    ("A12", 20),
    ("A27", 25),
    ("A78", 15),
    ("A89", 15),
    ("B01", 20),
    ("B12", 20),
    ("B2B7P", 25),
    ("B2B7S", 25),
    ("B7PB8", 25),
    ("B7SB8", 25),
    ("B89", 15),
    ("C01", 20),
    ("C12", 20),
    ("C26", 25),
    ("C67", 15),
    ("ASM01", 25),
    ("INSP01", 25),
    ("INSP02", 25),
    ("GA9", 15),
    ("GB9", 15),
    ("C7PKG", 15),
    ("PKG01", 15),
    ("PKG02", 15),
    ("RWK_RET", 10),
    ("SBUF", SBUF_CAP),
]
BUFFERS = dict(_BUFFER_ROWS)


def check_config(machine_rows, buffer_rows):
    """Validate roster shape; duplicate machine name or cap<=0 -> ValueError."""
    names = [n for n, _ in machine_rows]
    if len(set(names)) != len(names):
        raise ValueError("duplicate machine name in config")
    for n, m in machine_rows:
        if m["buffer_cap"] is not None and m["buffer_cap"] <= 0:
            raise ValueError(f"machine {n} has non-positive buffer cap")
    bnames = [n for n, _ in buffer_rows]
    if len(set(bnames)) != len(bnames):
        raise ValueError("duplicate buffer name in config")
    for n, cap in buffer_rows:
        if cap <= 0:
            raise ValueError(f"buffer {n} has non-positive cap")


check_config(_MACHINE_ROWS, _BUFFER_ROWS)
if len(MACHINES) != N_MACHINES or len(BUFFERS) != N_BUFFERS:
    raise ValueError("roster size mismatch vs N_MACHINES/N_BUFFERS")
if set(MACHINE_INDEX) != set(MACHINES):
    raise ValueError("MACHINE_INDEX does not cover MACHINES exactly")


# MINIPRO-34 physics couplings (all default OFF; schema v3). Normative
# coefficient table: .omo/plans/minipro-34-top4-couplings.md Scope — the
# values below are verbatim, invented nothing. twin.py reads every
# coefficient ONLY via COUPLING_Xn["key"] subscriptions, never literals.
COUPLING_X1A: dict[str, Any] = {
    "enabled": False,
    "alpha_cu": 0.00393,
    "k_cu_scale": 0.3,
    "tau_th": 12,
    "t_amb": 25.0,
    "i_base": 50.0,
}
COUPLING_X1B: dict[str, Any] = {
    "enabled": False,
    "t_rated_offset": 12.0,
    "kappa_der": 0.01,
    "trip_offset": 30.0,
    "reset_offset": 5.0,
    "e_trip": 150.0,
    "trip_code": "ELEC/MOTOR_OVLD",
    "i_delay_mult": 1.25,
}
COUPLING_X2: dict[str, Any] = {
    "enabled": False,
    "mu_bv": 0.2,
    "lambda_tv": 0.3,
    "v_ref": 1.0,
    "t_warn_offset": -10.0,
    "alpha_b": 1 / 200,
    "b_warn": 0.7,
}
COUPLING_X3: dict[str, Any] = {
    "enabled": False,
    "f_0": 1.0,
    "zeta": 1.0,
    "w_knee": 0.8,
    "alpha_w": 1 / 200,
    "r_0": 0.0,
    "rho": 1.4,
}
COUPLING_X4: dict[str, Any] = {
    "enabled": False,
    "inrush_mult": 5.0,
    "tau_inr": 2,
    "kappa_sag": 0.03,
}


def _class_mean_base(cls):
    vals = [entry["base"] for _, entry in _MACHINE_ROWS if entry["class"] == cls]
    return sum(vals) / len(vals)


# Derived per-class tables (computed once at import; twin.py subscribes,
# never recomputes): I_rated = class mean base / i_base; dT = band top -
# t_amb; k_cu = k_cu_scale * dT / I_rated^2; T_rated = band top +
# t_rated_offset; T_trip/reset = T_rated + trip/reset_offset;
# T_warn = T_rated + t_warn_offset.
COUPLING_X1A["I_rated"] = {
    cls: _class_mean_base(cls) / COUPLING_X1A["i_base"] for cls in TEMP_RANGES
}
COUPLING_X1A["dT"] = {
    cls: TEMP_RANGES[cls][1] - COUPLING_X1A["t_amb"] for cls in TEMP_RANGES
}
COUPLING_X1A["k_cu"] = {
    cls: COUPLING_X1A["k_cu_scale"]
    * COUPLING_X1A["dT"][cls]
    / COUPLING_X1A["I_rated"][cls] ** 2
    for cls in TEMP_RANGES
}
COUPLING_X1B["T_rated"] = {
    cls: TEMP_RANGES[cls][1] + COUPLING_X1B["t_rated_offset"] for cls in TEMP_RANGES
}
COUPLING_X1B["T_trip"] = {
    cls: COUPLING_X1B["T_rated"][cls] + COUPLING_X1B["trip_offset"]
    for cls in TEMP_RANGES
}
COUPLING_X1B["T_reset"] = {
    cls: COUPLING_X1B["T_rated"][cls] + COUPLING_X1B["reset_offset"]
    for cls in TEMP_RANGES
}
COUPLING_X2["T_warn"] = {
    cls: COUPLING_X1B["T_rated"][cls] + COUPLING_X2["t_warn_offset"]
    for cls in TEMP_RANGES
}

# Float bounds per coupling key: (lo, hi, lo_inclusive, hi_inclusive).
_COUPLING_FLOAT_BOUNDS = {
    "X1A": {
        "alpha_cu": (0.0, 1.0, False, True),
        "k_cu_scale": (0.0, 2.0, True, True),
        "t_amb": (-50.0, 100.0, True, True),
        "i_base": (0.0, float("inf"), False, True),
    },
    "X1B": {
        "t_rated_offset": (-50.0, 50.0, True, True),
        "kappa_der": (0.0, 1.0, True, False),
        "trip_offset": (0.0, 200.0, False, True),
        "reset_offset": (0.0, 200.0, True, True),
        "e_trip": (0.0, float("inf"), False, True),
        "i_delay_mult": (1.0, 2.0, True, True),
    },
    "X2": {
        "mu_bv": (0.0, 2.0, True, True),
        "lambda_tv": (0.0, 2.0, True, True),
        "v_ref": (0.0, float("inf"), False, True),
        "t_warn_offset": (-50.0, 50.0, True, True),
        "alpha_b": (0.0, 1.0, False, True),
        "b_warn": (0.0, 1.0, True, True),
    },
    "X3": {
        "f_0": (0.0, float("inf"), False, True),
        "zeta": (0.0, 5.0, True, True),
        "w_knee": (0.0, 1.0, True, True),
        "alpha_w": (0.0, 1.0, False, True),
        "r_0": (0.0, 1.0, True, True),
        "rho": (0.0, 5.0, True, True),
    },
    "X4": {
        "inrush_mult": (1.0, 10.0, True, True),
        "kappa_sag": (0.0, 1.0, True, False),
    },
}
_COUPLING_INT_KEYS = {("X1A", "tau_th"): (1, 1000), ("X4", "tau_inr"): (1, 1000)}
_COUPLING_DERIVED_KEYS = {
    "X1A": ("I_rated", "dT", "k_cu"),
    "X1B": ("T_rated", "T_trip", "T_reset"),
    "X2": ("T_warn",),
    "X3": (),
    "X4": (),
}


def _check_coupling_number(name, key, v, lo, hi, lo_inc, hi_inc):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or math.isnan(v):
        raise ValueError(f"coupling {name}[{key!r}] must be a number, got {v!r}")
    if v < lo or (not lo_inc and v == lo) or v > hi or (not hi_inc and v == hi):
        raise ValueError(f"coupling {name}[{key!r}]={v!r} out of range")


def check_couplings(couplings):
    """Validate coupling tables; unknown coupling/key or out-of-range -> ValueError."""
    if not isinstance(couplings, dict):
        raise ValueError(f"couplings must be a dict, got {couplings!r}")  # noqa: TRY004
    for name, table in couplings.items():
        if name not in _COUPLING_FLOAT_BOUNDS:
            raise ValueError(f"unknown coupling {name!r}")
        if not isinstance(table, dict):
            raise ValueError(  # noqa: TRY004
                f"coupling {name} must be a dict, got {table!r}"
            )
        bounds = _COUPLING_FLOAT_BOUNDS[name]
        allowed = set(bounds) | {"enabled"} | set(_COUPLING_DERIVED_KEYS[name])
        allowed |= {k for (n, k) in _COUPLING_INT_KEYS if n == name}
        if name == "X1B":
            allowed.add("trip_code")
        for key in table:
            if key not in allowed:
                raise ValueError(f"coupling {name} has unknown key {key!r}")
        for key in (
            "enabled",
            *bounds,
            *[k for (n, k) in _COUPLING_INT_KEYS if n == name],
        ):
            if key not in table:
                raise ValueError(f"coupling {name} missing key {key!r}")
        if not isinstance(table["enabled"], bool):
            raise ValueError(  # noqa: TRY004
                f"coupling {name}['enabled'] must be bool"
            )
        for key, (lo, hi, lo_inc, hi_inc) in bounds.items():
            _check_coupling_number(name, key, table[key], lo, hi, lo_inc, hi_inc)
        for (n, key), (lo, hi) in _COUPLING_INT_KEYS.items():
            if n != name:
                continue
            v = table[key]
            if isinstance(v, bool) or not isinstance(v, int) or not lo <= v <= hi:
                raise ValueError(f"coupling {name}[{key!r}]={v!r} out of range")
        if name == "X1B" and table["trip_code"] != "ELEC/MOTOR_OVLD":
            raise ValueError(
                f"coupling X1B['trip_code']={table['trip_code']!r} unknown"
            )
        for key in _COUPLING_DERIVED_KEYS[name]:
            if key not in table:
                continue
            grid = table[key]
            if not isinstance(grid, dict) or not grid:
                raise ValueError(f"coupling {name}[{key!r}] must be a class table")
            for cls, v in grid.items():
                if cls not in TEMP_RANGES:
                    raise ValueError(f"coupling {name}[{key!r}] unknown class {cls!r}")
                _check_coupling_number(
                    name, f"{key}[{cls}]", v, 0.0, float("inf"), False, True
                )


check_couplings(
    {
        "X1A": COUPLING_X1A,
        "X1B": COUPLING_X1B,
        "X2": COUPLING_X2,
        "X3": COUPLING_X3,
        "X4": COUPLING_X4,
    }
)
