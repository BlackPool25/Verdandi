"""Twin-only constants — SIM_SPEC Table 3.1 + twin scalars (T4).

Twin subset ONLY: per-machine operating points, buffers, AGV/SBUF, fault
ranges, state offsets. No detector/walk/PCMCI/narration constants live here
(downstream milestones own them). src/twin.py MUST import these, never
hardcode the same value twice (TECHNICAL.md config table).

Machine entry keys: class, base, sigma, cycle (cycle_steps), mttf, mttr,
buffer_cap (buffer after machine; None = sink + rework tap), transit
(nominal transit steps to next; None = sink).
"""

# Episode / calibration scalars (SIM_SPEC Table 3.1 header + §2.3).
T = 300
CAL_WIN = 120
N_MACHINES = 26
N_BUFFERS = 26
N_STREAMS = 36

# Topology-A schema version (MINIPRO-33): v2 = 26-machine roster. v1
# 32-machine baselines are V1_NON_COMPARABLE, never asserted equal.
TWIN_SCHEMA = 2
CODE_VERSION = "twin-2.1.0-topology-A"

# INSP0 holds each part exactly this many steps before late-verdict release.
INSPECT_DELAY_STEPS = 3

# Shared resources (SIM_SPEC §2.2).
AGV_CAP = 2
AGV_STEPS = (4, 8)  # ints: uniform transit per trip, sampled on rng_agv stream
SBUF_CAP = 30
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
_MACHINE_ROWS = [
    ("A0", _row("feed", 50.0, 1.0, 4, 2000, 15, 20, 2)),
    ("A1", _row("form", 60.0, 1.2, 5, 1500, 12, 20, 2)),
    ("A2", _row("process", 70.0, 1.5, 6, 800, 20, 25, 3)),
    ("A7", _row("process", 70.0, 1.5, 6, 800, 20, 25, 3)),
    ("A8", _row("finish", 55.0, 1.1, 4, 1200, 10, 15, 3)),
    ("A9", _row("inspect-tail", 48.0, 1.4, 3, 1500, 8, 15, None)),
    ("B0", _row("feed", 50.0, 1.0, 4, 2000, 15, 20, 2)),
    ("B1", _row("form", 60.0, 1.2, 5, 1500, 12, 20, 2)),
    ("B2", _row("process", 70.0, 1.5, 6, 800, 20, 25, 3)),
    ("B7P", _row("process", 70.0, 1.5, 6, 800, 20, 25, 3)),
    ("B7S", _row("process", 70.0, 1.5, 6, 800, 20, 25, 3)),
    ("B8", _row("finish", 55.0, 1.1, 4, 1200, 10, 15, 3)),
    ("B9", _row("inspect-tail", 48.0, 1.4, 3, 1500, 8, 15, None)),
    ("C0", _row("feed", 50.0, 1.0, 4, 2000, 15, 20, 2)),
    ("C1", _row("form", 60.0, 1.2, 5, 1500, 12, 20, 2)),
    ("C2", _row("process", 70.0, 1.5, 6, 800, 20, 25, 3)),
    ("C6", _row("process", 70.0, 1.5, 6, 800, 20, 25, 3)),
    # C7 "finish" label is line shorthand only (Table 3.1 note); params are inspect.
    # buffer_cap=15 (tail cap governs dedicated _C7TAIL store); mttr=8 is repair, not cap.
    ("C7", _row("inspect-tail", 48.0, 1.4, 3, 1500, 8, 15, None)),
    ("PKG0", _row("assembly-kit", 65.0, 1.3, 5, 1000, 12, 25, 2)),
    ("PKG1", _row("finish", 55.0, 1.1, 4, 1200, 10, 15, None)),
    ("PKG2", _row("finish", 55.0, 1.1, 4, 1200, 10, 15, None)),
    # ASM0 cycle 5 explicit per Table 3.1 (assembly/kit).
    ("ASM0", _row("assembly-kit", 65.0, 1.3, 5, 1000, 12, 25, 2)),
    ("ASM1", _row("assembly-join", 66.0, 1.3, 6, 1000, 12, 25, 2)),
    ("INSP0", _row("test", 45.0, 2.0, 2, 1200, 10, 25, 2)),
    # ASM2 σ=2.0 kept noisy per spec — do not quiet it; VETO_ASM2 compensates (§7).
    ("ASM2", _row("test", 45.0, 2.0, 3, 1200, 10, None, None)),
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
