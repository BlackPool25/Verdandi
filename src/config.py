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
N_MACHINES = 32
N_BUFFERS = 31
N_STREAMS = 36

# Shared resources (SIM_SPEC §2.2).
AGV_CAP = 2
AGV_STEPS = (4, 8)  # ints: uniform transit per trip, sampled on rng_place stream
SBUF_CAP = 30
# Owner ruling 2026-09-12: process/finish divert, feed/form never; inspect
# tails included (draft reviewer note: Scope/Config lines govern).
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
    return {"class": cls, "base": base, "sigma": sigma, "cycle": cycle,
            "mttf": mttf, "mttr": mttr, "buffer_cap": buffer_cap,
            "transit": transit}


# Per-machine Table 3.1 rows: (name, entry). Rows expand the class lines of
# Table 3.1 (feed A0/B0/C0; form A1/B1/C1; process A2–A7/B2–B7/C2–C6;
# finish A8/B8; inspect-tail A9/B9/C7; ASM0–2; RWK0).
_MACHINE_ROWS = [
    ("A0", _row("feed", 50.0, 1.0, 4, 2000, 15, 20, 2)),
    ("A1", _row("form", 60.0, 1.2, 5, 1500, 12, 20, 2)),
    ("A2", _row("process", 70.0, 1.5, 6, 800, 20, 25, 3)),
    ("A3", _row("process", 70.0, 1.5, 6, 800, 20, 25, 3)),
    ("A4", _row("process", 70.0, 1.5, 6, 800, 20, 25, 3)),
    ("A5", _row("process", 70.0, 1.5, 6, 800, 20, 25, 3)),
    ("A6", _row("process", 70.0, 1.5, 6, 800, 20, 25, 3)),
    ("A7", _row("process", 70.0, 1.5, 6, 800, 20, 25, 3)),
    ("A8", _row("finish", 55.0, 1.1, 4, 1200, 10, 15, 3)),
    ("A9", _row("inspect-tail", 48.0, 1.4, 3, 1500, 8, 15, None)),
    ("B0", _row("feed", 50.0, 1.0, 4, 2000, 15, 20, 2)),
    ("B1", _row("form", 60.0, 1.2, 5, 1500, 12, 20, 2)),
    ("B2", _row("process", 70.0, 1.5, 6, 800, 20, 25, 3)),
    ("B3", _row("process", 70.0, 1.5, 6, 800, 20, 25, 3)),
    ("B4", _row("process", 70.0, 1.5, 6, 800, 20, 25, 3)),
    ("B5", _row("process", 70.0, 1.5, 6, 800, 20, 25, 3)),
    ("B6", _row("process", 70.0, 1.5, 6, 800, 20, 25, 3)),
    ("B7", _row("process", 70.0, 1.5, 6, 800, 20, 25, 3)),
    ("B8", _row("finish", 55.0, 1.1, 4, 1200, 10, 15, 3)),
    ("B9", _row("inspect-tail", 48.0, 1.4, 3, 1500, 8, 15, None)),
    ("C0", _row("feed", 50.0, 1.0, 4, 2000, 15, 20, 2)),
    ("C1", _row("form", 60.0, 1.2, 5, 1500, 12, 20, 2)),
    ("C2", _row("process", 70.0, 1.5, 6, 800, 20, 25, 3)),
    ("C3", _row("process", 70.0, 1.5, 6, 800, 20, 25, 3)),
    ("C4", _row("process", 70.0, 1.5, 6, 800, 20, 25, 3)),
    ("C5", _row("process", 70.0, 1.5, 6, 800, 20, 25, 3)),
    ("C6", _row("process", 70.0, 1.5, 6, 800, 20, 25, 3)),
    # C7 "finish" label is line shorthand only (Table 3.1 note); params are inspect.
    ("C7", _row("inspect-tail", 48.0, 1.4, 3, 1500, 8, 15, None)),
    # ASM0 cycle 5 explicit per Table 3.1 (assembly/kit).
    ("ASM0", _row("assembly-kit", 65.0, 1.3, 5, 1000, 12, 25, 2)),
    ("ASM1", _row("assembly-join", 66.0, 1.3, 6, 1000, 12, 25, 2)),
    # ASM2 σ=2.0 kept noisy per spec — do not quiet it; VETO_ASM2 compensates (§7).
    ("ASM2", _row("test", 45.0, 2.0, 3, 1200, 10, None, None)),
    ("RWK0", _row("rework", 62.0, 1.6, 8, 900, 18, 10, 5)),
]

for _tail in ("A9", "B9", "C7"):
    for _name, _entry in _MACHINE_ROWS:
        if _name == _tail:
            _entry["transit"] = AGV_STEPS

MACHINES = dict(_MACHINE_ROWS)

# Canonical index order: A0–A9=0–9, B0–B9=10–19, C0–C7=20–27, ASM0–2=28–30, RWK0=31.
MACHINE_INDEX = (
    {f"A{i}": i for i in range(10)}
    | {f"B{i}": 10 + i for i in range(10)}
    | {f"C{i}": 20 + i for i in range(8)}
    | {"ASM0": 28, "ASM1": 29, "ASM2": 30, "RWK0": 31}
)

# Buffer roster: 29 gap buffers + 1 rework return + SBUF = 31 (SIM_SPEC §2.2).
# Gap caps mirror the upstream machine's "buffer after (cap)"; tail gateways
# GA9/GB9 cap 15; C7 tail stages in the C67 gap buffer (short-line shorthand,
# tail cap 15 governs the shared staging buffer over C6's nominal 25).
_BUFFER_ROWS = (
    [(f"A{i}{i + 1}", 25 if 2 <= i <= 7 else (20 if i <= 1 else 15)) for i in range(9)]
    + [(f"B{i}{i + 1}", 25 if 2 <= i <= 7 else (20 if i <= 1 else 15)) for i in range(9)]
    + [(f"C{i}{i + 1}", 25 if 2 <= i <= 5 else (20 if i <= 1 else 15)) for i in range(7)]
    + [("ASM01", 25), ("ASM12", 25), ("GA9", 15), ("GB9", 15)]
    + [("RWK_RET", 10), ("SBUF", SBUF_CAP)]
)
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
