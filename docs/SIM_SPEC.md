# SIM_SPEC — factory-flow simulation spec, topology-A short+branchy plant (REQ-010, build-ready)

Status: normative for the build twin. A builder implements this file alone,
without reading `spike/`. `spike/` stays quarantine (never merge).
Traceability: REQ-010 (SRS §REQ-010, SDD §2.1/§2.3, TEST_PLAN TST-003).
Measured values carried verbatim from `docs/TECHNICAL.md`,
`docs/ARCHITECTURE.md`, `spike/REPORT_BATTERY.md`, `spike/REPORT_CLOSEOUT.md`,
and (topology-A) `docs-battery-topology-A-full182.json` + `src/config.py`.
Bars restated, never softened (§11).

> Single-writer note (MINIPRO-33 / MINIPRO-30 protocol): MINIPRO-33 owns
> sections 2-7 until merged; MINIPRO-30 rebases after. Rebase protocol: Todo 11
> (freeze-readiness pack, `docs/M0B_FREEZE_INPUT.md`) lists the exact SIM_SPEC
> commit MINIPRO-30 rebases onto; MINIPRO-30 must not edit §§2–7 before that
> commit lands on main. Detector thresholds (§7.1–§7.2) and MINIPRO-34/35
> sections are untouched by this amendment.

Topology-A lineage (normative pins): TWIN_SCHEMA=2,
CODE_VERSION='twin-2.1.0-topology-A' (exact literal, never '2.x'),
INSPECT_DELAY_STEPS=3. Battery IDs 'topology-A-quick16' (16-row smoke) +
'topology-A-full182' (full manifest); F-21-on-B2 seed-777 digest
`523b0b9e71f47d355cf4e4f4b7f73d29c333747d253d3b016c1edf2957bbd8c4`;
joined battery digest
`64af2d24a538d2c7c217b8c244835fe230ec902dccbc8632f0e2b1aa8ddf6cb6`.
v1 32-machine baselines (flow digest `962b9c54d022`, demo digest `d2b4fb23…`)
are V1_NON_COMPARABLE (schema v1), never asserted equal.
Retime (owner-approved option C, bounded MINIPRO-24): AGV_CAP 3, TAKT5
single-takt line balance (cycles below), AGV drain grace 8
(`AGV_DRAIN_GRACE`), duty plant-mean over 24 machines with standby scope
{B7S, RWK0} excluded (`STANDBY_EXCLUDED`).

Hand-rolled SimPy only (ADR-0012 rejected FactorySimPy: no trace/fault/RNG
API). Real `simpy.Resource` / `simpy.Store` objects, not abstract delays.

## 1. Scope and non-goals

1.1. This spec defines the entire factory flow twin: 26 machines in 3
shortened lines + packaging fork + assembly cell (with inspection delay) +
rework loop + shared buffer/AGV resource,
mass-flow-conserved propagation, finite buffers with blocking/starving,
per-machine cycle times, breakdown/repair, seeded fault injection with free
ground truth, and the full multi-channel data taxonomy (§8).
1.2. The twin NEVER issues safety-restart clearance (human-only, SPEC FR-9).
1.3. Non-goals (killed, do not rebuild): FactorySimPy twin (REJECTED per
ADR-0012), learned-graph detection, MP-discord detector (F1 0.063, killed),
GDN (torch not importable, skipped), GPU path, live stream, point-adjusted
scoring (inadmissible, never use).

## 2. Plant layout (normative, 26 machines, topology-A)

2.1. Lines (parallel, independent feeds, join at assembly):

- Line A (6 machines): A0→A1→A2→A7→A8→A9, feed raw stock. Roles: feed, form,
  process ×2, finish, inspect-tail. Gaps rewired: A2→A7 via gap buffer A27.
- Line B (7 machines): B0→B1→B2→{B7P,B7S}→B8→B9, same feed/form head with a
  redundant overflow-failover pair in the process midsection (B7P primary,
  B7S spare). Fork gaps B2B7P/B2B7S, join gaps B7PB8/B7SB8.
- Line C (5 machines): C0→C1→C2→C6→C7, short line (feed, form, process ×2,
  inspect-tail). Gap rewired: C2→C6 via gap buffer C26.
- Packaging fork (3 machines): PKG0 (fork, assembly-kit class) fed from C7
  output via buffer C7PKG; PKG1/PKG2 (packaging-sink tails: parts SINK here
  as packaged goods, `flow_stats` packaged+=1, never rejoin kit, never
  SBUF-divert — `_TAILS` extended to (A9,B9,C7,PKG1,PKG2)). Split rule
  (normative): per-episode counter `shared['pkg_rr']` reset to 0 at episode
  start; first part → PKG1, then strict alternation; if the target tail
  buffer is full → try the other tail; if both full → PKG0 holds BLOCKED
  (no loss, no SBUF).
- Assembly cell (4 machines): ASM0 (kitting from A9/B9/C7), ASM1 (join),
  INSP0 (inspection delay, test class), ASM2 (test). Order is
  ASM0→ASM1→INSP0→ASM2; INSP0 holds each part exactly INSPECT_DELAY_STEPS=3
  steps then releases (late verdict at release, §5). ASM0 pulls one part
  each from A9, B9, C7 output buffers.
- Rework loop (1 machine): RWK0. ASM2-test rejects route back via
  `ASM2→RWK0→ASM0` buffer path; reworked parts re-enter ASM0 kitting queue.

Total: 6 + 7 + 5 + 3 + 4 + 1 = 26 machines (18 line machines + 3 packaging
+ 1 inspection-delay + 4 cell). The Linear branch slug keeps '22-machines'
for traceability; the 26 derivation is recorded openly here — phenomena
preserved over exact-22.

Exact normative counts: N_MACHINES=26, N_BUFFERS=26, manifest 26×7=182 rows,
frontend 28 nodes (26+SBUF+_C7TAIL), EXPECTED_EDGE_COUNT=31.

2.2. Buffers and shared resources:

- Every inter-machine gap has one finite FIFO `simpy.Store` (capacity per
  Table 3.1). 16 line-gap + 5 cell (ASM01, INSP01, INSP02, GA9, GB9) + 3
  packaging (C7PKG, PKG01, PKG02) + 1 rework return + 1 shared
  overflow buffer = 26 named buffers:
  A01(20) A12(20) A27(25) A78(15) A89(15); B01(20) B12(20) B2B7P(25)
  B2B7S(25) B7PB8(25) B7SB8(25) B89(15); C01(20) C12(20) C26(25) C67(15);
  ASM01(25) INSP01(25) INSP02(25) GA9(15) GB9(15); C7PKG(15) PKG01(15)
  PKG02(15); RWK_RET(10) SBUF(30).
- Shared resource: AGV pool, `simpy.Resource(capacity=3)` (AGV_CAP=3,
  owner-approved retime). Any transfer
  from a line-tail buffer (A9, B9, C7) to ASM0 kitting must `request()` an
  AGV, hold for `agv_steps` (Table 3.1), then release. AGV queueing is
  logged as wait time per part. Drain accounting: dispatcher admits a spawn
  only if it lands by T+AGV_DRAIN_GRACE (grace 8); the drain phase runs
  pending AGV transfers until T+8 with obs shapes intact at T.
- Shared overflow buffer SBUF (capacity 30, `simpy.Store`): when any
  tail buffer is full, the upstream machine may divert to SBUF only if its
  class allows it (process/finish classes yes; feed/form no; PKG tails
  never — sinks ride no divert path). SBUF drains
  to ASM0 when an AGV is free. SBUF occupancy is logged.
- Line-B failover rule (normative): at cycle-start route to B7S iff B7P
  state is DOWN or the B7P downstream buffer (B7PB8) is full (reason
  OVERFLOW), else B7P; emit FAILOVER event
  `{t, from:'B7P', to, reason:'DOWN'|'OVERFLOW'}`; throughput counted once
  at B8 intake regardless of source (no double-count); BLOCKED/STARVED
  propagation at B8 unchanged; if BOTH pair members are DOWN/full, parts
  queue in fork buffers B2B7P/B2B7S (cap 25 each) and B2 goes BLOCKED on
  full (backpressure, no loss, no SBUF).

2.3. Time: discrete steps, `T=300` per episode. First `CAL_WIN=120` steps
are clean calibration (fault injection forbidden at `t < 120`; battery
asserts this). Fault windows live in `t ∈ [120, 300)`.

2.4. Flow semantics (normative, replaces signal-copy echo):

- Parts are discrete WIP entities moving machine→buffer→machine.
- BLOCKING: if downstream buffer is full when a machine finishes a cycle,
  the machine blocks (holds the part, state=BLOCKED, consumes cycle time,
  emits no new output) until space frees.
- STARVING: if upstream buffer is empty when a machine is ready to start,
  the machine starves (state=STARVED, idle) until a part arrives.
- ASM0 additionally starves unless all three tail inputs (A9, B9, C7 or
  via SBUF) each have ≥1 part (kitting constraint).
- Propagation delay = cycle times + buffer queue time + AGV wait, never a
  fixed lag constant. Nominal per-hop transit is documented per Table 3.1
  for detector window sizing only.

## 3. Per-machine parameters (normative defaults, log any change)

Machine classes: feed, form, process, finish, inspect-tail, assembly-kit,
assembly-join, test, rework. Cycle times and buffers per class.
Every coefficient below is traceable to `src/config.py` (`_MACHINE_ROWS` /
`_BUFFER_ROWS`); the twin imports them and never duplicates values
(stale-token CI bans hardcoded Table 3.1 values outside `config.py`).

| ID | Class | base | σ | cycle_steps | MTTF steps | MTTR steps | Buffer after (cap) | Nominal transit to next |
|---|---|---|---|---|---|---|---|---|
| A0, B0, C0 | feed | 50.0 | 1.0 | 5 | 2000 | 15 | 20 | 2 |
| A1, B1, C1 | form | 60.0 | 1.2 | 5 | 1500 | 12 | 20 | 2 |
| A2, A7, B2, C2, C6 | process | 70.0 | 1.5 | 5 | 800 | 20 | 25 | 3 |
| B7P | process | 70.0 | 1.5 | 5 | 800 | 20 | 25 | 3 |
| B7S | process (spare) | 70.0 | 1.5 | 6 | 800 | 20 | 25 | 3 |
| A8, B8 | finish | 55.0 | 1.1 | 5 | 1200 | 10 | 15 | 3 |
| PKG1, PKG2 | finish (packaging sink) | 55.0 | 1.1 | 10 | 1200 | 10 | 15 | None (sink) |
| A9, B9 | inspect-tail | 48.0 | 1.4 | 5 | 1500 | 8 | tail 15 | AGV 4–8 |
| C7 | inspect-tail | 48.0 | 1.4 | 5 | 1500 | 8 | tail 15 | AGV 4–8 |
| PKG0 | assembly-kit (fork) | 65.0 | 1.3 | 5 | 1000 | 12 | 25 | 2 |
| ASM0 | assembly-kit | 65.0 | 1.3 | 5 | 1000 | 12 | 25 | 2 |
| ASM1 | assembly-join | 66.0 | 1.3 | 5 | 1000 | 12 | 25 | 2 |
| INSP0 | test (delay node) | 45.0 | 2.0 | 2 | 1200 | 10 | 25 | 2 |
| ASM2 | test | 45.0 | 2.0 | 5 | 1200 | 10 | — (sink + rework tap) | — |
| RWK0 | rework | 62.0 | 1.6 | 8 | 900 | 18 | return 10 | 5 |

TWIN_SCHEMA=2, CODE_VERSION='twin-2.1.0-topology-A' (exact literal),
INSPECT_DELAY_STEPS=3 — all in `src/config.py`; every battery number is
logged with (schema_version=2, battery_id).

TAKT5 retime note (owner-approved option C, bounded MINIPRO-24): single-takt
line balance at takt=5 (the form/kit cadence). Feed 4→5, process 6→5,
finish 4→5, inspect-tail 3→5, assembly-join 6→5, test (ASM2) 3→5,
packaging-sink (PKG1/PKG2) 4→10 (PKG0 at 5 round-robins, each tail fed
1-in-10). Frozen at old values: B7S cycle 6 (spare, excluded from the duty
mean), INSP0 cycle 2 (delay-paced via INSPECT_DELAY_STEPS, cycle knob dead),
RWK0 cycle 8 (rework loop, excluded from the duty mean). Classes, MTTF/MTTR,
buffer caps, transits, and signal coefficients frozen.

Notes:

- `base`, `σ` fix the clean operating point. Envelope is `base ± 3σ`
  (matches detector §7 on clean data). ASM2 σ=2.0 is the documented
  known-noisy tail; VETO_ASM2 (§7) compensates, do not quiet ASM2 by
  shrinking its σ. VETO rule renamed from VETO_M5 (6-machine era) with
  identical 2×-margin semantics. INSP0 shares the test-class σ=2.0
  operating point; its delay behavior is pacing, not noise shaping.
- `MTTF/MTTR`: natural breakdowns sampled as geometric per step
  (`p_fail = 1/MTTF` per running step, `p_repair = 1/MTTR` per down step),
  independent of injected faults. State DOWN preempts BLOCKED/STARVED.
  Natural-breakdown steps are flagged in event logs, excluded from fault
  ground-truth windows.
- AGV transit `agv_steps` uniform in [4,8] per trip (sampled on
  `rng_place` stream). AGV_CAP=3.
- Every machine × every fault class in its row of §5 must be injected ≥1
  per acceptance battery (TST-003 flow-coverage). 26 machines × 7 classes
  = 182-row manifest; representative-machine shorthand in §5 defines the
  mandatory subset, full cross product is the target.

## 4. Signal generation (normative equations)

4.1. Clean signal for machine `i` at step `t`:

```
phase_i(t)  = 2π · (t mod cycle_i) / cycle_i
clean_i(t)  = base_i + 0.5·σ_i · sin(phase_i(t)) + AR1_i(t)
AR1_i(t)    = 0.6 · AR1_i(t-1) + ε,  ε ~ Normal(0, σ_i · 0.5), AR1_i(0) = 0
obs_i(t)    = clean_i(t) + state_i(t) + faultdev_i(t)
state_i(t)  = −2σ_i if STARVED, −σ_i if BLOCKED (held part, no fresh work),
              −3σ_i if DOWN, else 0
faultdev_i  = §5 deviation at origin machine only
```

Downstream machines NEVER receive a scaled copy of the origin deviation.
They observe consequences only: queue growth/shrink in shared buffers,
BLOCKED/STARVED state excursions, throughput dips, delayed part arrivals,
and the origin part physically arriving late or degraded (quality flag
carried on the part entity, §8 channel 4).

4.2. WHY the old echo is gone (audit finding, normative):

The 6-machine spike (`spike/battery_rq1_rq2.py` lines 44–72) used
`v += fault["mag"] * (0.45 ** lag)`: a pure signal copy with geometric
decay (`base 10+2m + noise`, no buffers, no queues, no starving/blocking).
Audit findings that force replacement:

- (a) It violates mass conservation: downstream machines show fault
  energy without any part carrying it, so throughput and quality channels
  stay clean while the signal channel alarms. A detector tuned on this
  learns a signature that cannot exist in the plant.
- (b) It cannot produce BLOCKING or STARVING, the two dominant real
  propagation modes. Queue-delay was a post-hoc additive fudge, not a
  buffer occupancy consequence.
- (c) Decay `0.45^lag` is a free parameter with no physical meaning;
  hop count and cycle-time differences change real attenuation, fixed
  decay does not.
- (d) Rework and shared-resource contention (AGV) have no representation
  in signal-copy at all.

Replacement: fault effects propagate ONLY via WIP movement, buffer
occupancy, machine states, and part-carried quality flags. The data
taxonomy (§8) records all of these so detection uses the same channels a
real plant historian provides.

4.3. Fault-window placement: `t0` uniform in `[120, 300−dur]`, windows may
overlap across episodes, never within one episode on the same machine
(≥5-step gap between windows on the same machine). B2 hosting F-21 (drift
[150,162)) + F-25 (breakdown [190,202)) satisfies the gap rule.
4.4. Episode record: `{seed, T: 300, cal_win: 120, schema_version: 2,
code_version: 'twin-2.1.0-topology-A', machines: Table 3.1,
obs[26][300], states[26][300], buffers[26][300], agv_waits[], parts[],
faults[]}`. `faults[]` is free ground truth: `{fault_id, class, origin,
t0, dur, mag_sigma, extra:{d | drop_rate | mttr_mult | reject_rate}}`.
The replay digest canonical payload INCLUDES schema_version + code_version
alongside the partition subgraph obs (sorted keys, existing wall-clock
exclusions kept), so version tampering mismatches the digest by
construction. The twin bridge runs v2-only with an explicit v1-reject
error ('schema v1 non-comparable, rebaseline').

## 5. Fault-injection taxonomy (normative, 7 classes × representative machines)

Classes: spike, drift, bias, delay (slow-cycle), loss (drops), breakdown
(extended DOWN), quality (reject-rate). Each row must be injected ≥1 on
each listed representative machine per acceptance battery. Full cross
product (26 machines × 7 classes = 182 rows) is the target; rep=True pins
per the oracle table below.

| Class | Mechanism (origin machine) | Params | Representative machines (mandatory) | Downstream observable (via flow, not echo) |
|---|---|---|---|---|
| spike | `+mag·σ` rectangular pulse on origin obs | mag 4–7σ, dur 8–25 | A0(feed), A2(process), B2(process), C6(process), ASM1, RWK0 | degraded part flag travels; brief buffer dip downstream |
| drift | ramp to `mag·σ` on origin obs | mag 4–7σ end, dur 8–25 | B2 (F-21), A7, C2, ASM0 | growing STARVED gaps downstream as cycle output degrades |
| bias | constant `+mag·σ` on origin obs | mag 4–7σ, dur 8–25 | A7 (F-22), B8, ASM2 | sustained offset + buffer level shift |
| delay (slow-cycle) | origin `cycle_steps += d`, `d ∈ [3,6]` per step for window | dur 8–25 | C2 (F-23), A2, B2, ASM0, RWK0 | upstream BLOCKING cascade, downstream STARVING; arrival shift = `nominal + d` per hop |
| loss (drops) | 10–30% observation drops at origin + carried-part flag drops, clean-median imputation before detection (cal intact) | dur 8–25 | B7P (F-24), A8, C6, ASM1 | thinned signal; flip rises, F1 holds |
| breakdown | force state DOWN for window (`MTTR × mttr_mult`, `mult ∈ [1,3]`) | dur 8–25 | B2 (F-25), A7, C6, ASM1 | hard BLOCKED upstream + STARVED downstream; throughput zero at origin |
| quality (reject) | ASM2/RWK-path reject rate raised to 15–40% for window | dur 8–25 | B9 (F-26), A9, ASM2, RWK0 | rework buffer surge, ASM0 kitting starve, throughput dip at sink |

Oracle relocation map (dead B-midsection reps moved, survivors stay):
F-21 drift B5→B2 (t0=150 dur=12 mag 5.2), F-22 bias B6→A7 (t0=160 dur=12
mag 5.0), F-23 delay B4→C2 (t0=170 dur=12 d=4), F-24 loss B7→B7P (t0=180
dur=12 drop 0.2), F-25 breakdown B2 stays (t0=190 dur=12), F-26 quality B9
stays (t0=200 dur=12), F-06 spike A0 stays.

Late-label semantics (INSP0, normative): INSP0 sits ASM1→INSP0→ASM2
(buffers INSP01/INSP02, cap 25; old ASM12 buffer retired) and holds each
part exactly INSPECT_DELAY_STEPS=3 steps, then releases. Late verdict at
release: part flag OK→DEGRADE (or REJECT for active INSP0 quality windows,
which set REJECT at release and flow to ASM2's existing REJECT routing);
emits LATE_VERDICT event `{t, part, verdict}` in the release step AFTER the
put, BEFORE the obs write. Obs sampling at INSP0 is otherwise normal
(`_fault_dev` / `_sample_signal` apply to INSP0 origins). ALL 7 fault
classes are injectable on INSP0 via the generic machinery; late-label
semantics apply to flag-carrying outcomes (quality/degrade paths). INSP0
intake cap 25; full intake holds ASM1 BLOCKED (no loss).

M0-era restriction (delay/loss origins M1+ only, M0 base-classes only) is
superseded: every class above lists its own mandatory origins.

## 6. RNG discipline (normative, K4)

6.1. `SeedSequence` everywhere. Zero bare `default_rng(int)`.
6.2. Per episode with master `seed`:

```
ss = SeedSequence((seed,))
child = ss.spawn(36)  # [AR noise x26, retired x6, placement, drops, agv, breakdown]
rng_noise[i] = default_rng(child[i])   # i = noise index per MACHINE_INDEX below
rng_place    = default_rng(child[32])  # t0/mag/dur/d sampling
rng_drop     = default_rng(child[33])  # loss masks
rng_agv      = default_rng(child[34])  # AGV transit times
rng_fail     = default_rng(child[35])  # natural breakdown/repair draws
```

6.3. Do NOT seed with `SeedSequence((seed, hash(id)))` or any
process-string hash: closeout measured ±1pt F1 run-jitter from that
pattern. Spawn indices only.
6.4. Replay (§9) re-runs the same `seed` with the same code version and
causal-partition mask; 5× same-seed runs must show 0 diverge (K4 gate).

Noise-index remap table (verbatim, index = noise stream; children 26–31
retired, assert unread; 32 place / 33 drop / 34 agv / 35 fail unchanged):

| Machine | Index | Machine | Index | Machine | Index |
|---|---|---|---|---|---|
| A0 | 0 | B7S | 10 | PKG1 | 19 |
| A1 | 1 | B8 | 11 | PKG2 | 20 |
| A2 | 2 | B9 | 12 | ASM0 | 21 |
| A7 | 3 | C0 | 13 | ASM1 | 22 |
| A8 | 4 | C1 | 14 | INSP0 | 23 |
| A9 | 5 | C2 | 15 | ASM2 | 24 |
| B0 | 6 | C6 | 16 | RWK0 | 25 |
| B1 | 7 | C7 | 17 | (retired) | 26–31 |
| B2 | 8 | PKG0 | 18 | place/drop/agv/fail | 32/33/34/35 |
| B7P | 9 | | | | |

Survivor moves for the record: A7 7→3, A8 8→4, A9 9→5, B0 10→6, B1 11→7,
B2 12→8, B8 18→11, B9 19→12, C0 20→13, C1 21→14, C2 22→15, C6 26→16,
C7 27→17, ASM0 28→21, ASM1 29→22, ASM2 30→24, RWK0 31→25.

## 7. Detection, veto, walk (twin outputs feed these; thresholds verbatim)

7.1. Detector (quantile/IQR, mandatory per K2): per-machine, per-channel
(§8 channels 1–2; channels 3–7 feed walk context, not thresholds)
`Q_DET = max(q0.99, Q3 + 1.5·IQR)` computed on that machine's clean window
(`t < 120`). No global fixed threshold.
7.2. Veto-mask (fixed topology prior): ASM2 is known-noisy; ASM2 wins top-1
only with a 2× margin over the runner-up score (VETO_ASM2, ex-VETO_M5).
No other mask.
7.3. Walk: from the symptom machine upstream along flow edges (through
buffers, AGV links, and the rework return edge), depth ≤3 (WALK_DEPTH),
top-k prune at each hop (fan-out cap 8 for the assembly join). Echo
suppression is documentary for flow-conserved echoes within the transit
window.
7.4. Causal evidence only (never production edges): PCMCI ParCorr,
`tau_max=2`, `pc_alpha=0.05`, `α=0.01` RUN PER CAUSAL PARTITION (§10), not
on the full 26-node graph. PCMCI window floor N_FLOOR=800 (KQ1: 400
unstable, 800 stable). Flip gate <40% per partition.

Causal partitions (topology-A): `line-A` (A0,A1,A2,A7,A8,A9),
`line-B` (B0,B1,B2,B7P,B7S,B8,B9 — the B-pair lives inside line-B),
`line-C` (C0,C1,C2,C6,C7 plus the packaging branch PKG0,PKG1,PKG2),
`cell` (ASM0, ASM1, INSP0, ASM2, RWK0, plus tail inputs A9/B9/C7 as
boundary conditions). Cross-partition
edges allowed ONLY at `tails→ASM0` (AGV links) and `ASM2→RWK0→ASM0`
(rework), evaluated as pairwise boundary checks, never as full-graph
discovery.
Walk examples (relocated reps): drift at B2 walks B8→B7P→B2 within line-B
(the B-pair join is one hop; failover source B7S is walk context, not a
separate path); bias at A7 walks A8→A7 within line-A; delay at C2 walks
C6→C2 within line-C; loss at B7P walks B8→B7P (or via B7S on failover
windows, marked FAILOVER context); quality at B9 walks the inspect-tail
plus rework return edge; INSP0 late verdicts walk ASM2→INSP0→ASM1 in cell.

## 8. Data taxonomy (normative, multi-channel)

Every machine emits channels 1–5 per step; channels 6–7 are plant-level.
Detector thresholds (§7.1) apply to channels 1–2 only.

| # | Channel | Type | Range | Rate | Per machine-class notes |
|---|---|---|---|---|---|
| 1 | vibration/signal `obs` | float | `base ± 6σ` clamp | 1/step | all classes; ASM2 σ=2.0 noisy |
| 2 | temperature | float °C | 20–120 | 1/step | process: 60–95 nominal; feed/form: 20–45; assembly: 25–55; test/rework: 20–60 |
| 3 | throughput/counts | int parts/step | 0–1 (0–3 ASM0 kit) | 1/step | 1 on cycle completion, else 0; DOWN/BLOCKED/STARVED emit 0 |
| 4 | quality flag | enum {OK, DEGRADE, REJECT} | — | per part | inspect-tail/test set REJECT; origin fault sets DEGRADE carried downstream on the part; INSP0 late verdicts mutate at release (§5) |
| 5 | machine state | enum {RUN, BLOCKED, STARVED, DOWN} | — | 1/step + on-change event | BLOCKED = downstream full; STARVED = upstream empty (ASM0: any kit input empty); DOWN = breakdown |
| 6 | buffer level | int parts | 0–cap | 1/step per buffer (26 buffers) | includes SBUF + rework return buffer |
| 7 | event log | structured `{t, machine, event, detail}` | — | on-change | events: FAULT_START/END, BLOCK_ON/OFF, STARVE_ON/OFF, DOWN/UP, AGV_WAIT, REJECT_ROUTE, DIVERT_SBUF, FAILOVER, PACK_FORK, LATE_VERDICT |

Sampling: twin step = 1 sample for channels 1–3, 5–6. Channel 4 sampled
per part completion. Channel 7 is sparse/event-driven. No sub-step
sampling; SDD may downsample channels 1–2 (not 6–7) for PCMCI partitions
under the §10 budget.

## 9. Data contracts and JSON examples (normative keys, types, ranges)

Types: `machine ∈ {A0,A1,A2,A7,A8,A9, B0,B1,B2,B7P,B7S,B8,B9,
C0,C1,C2,C6,C7, PKG0,PKG1,PKG2, ASM0,ASM1,INSP0,ASM2,RWK0}`, `t` int step
in `[0,300)`, scores floats in `[0,1]`, `edge_id` string `"X->Y"` (flow
edge, buffer/AGV hops named e.g. `"A9~AGV~ASM0"`, rework `"ASM2~RWK0~ASM0"`,
fork/join `"B2->B7P"`, `"B7P->B8"`, packaging `"PKG0->PKG1"`).
One running example: fault `F-21` (drift, B2, t0=150, dur=12, mag=5.2σ).

Re-baselined pin (topology-A schema v2, battery `topology-A-full182`):
seed 777 F-21-on-B2 digest
`523b0b9e71f47d355cf4e4f4b7f73d29c333747d253d3b016c1edf2957bbd8c4`
(`code_version` 'twin-2.1.0-topology-A', `schema_version` 2, GT window
exact (150,162)). Detector peak/threshold figures in the examples below
are illustrative of the triple and contract format, not measured twin
output; the digest, GT window, schema, and code version are measured.
v1 32-machine digests are V1_NON_COMPARABLE, never asserted equal.

### 9.1. Alarm

```json
{
  "id": "A-2026-021",
  "machine": "B8",
  "t_start": 156,
  "t_end": 167,
  "detector_output": {
    "machine": "B8",
    "channel": "vibration",
    "threshold_qdet": 58.31,
    "peak_value": 61.4,
    "peak_t": 159,
    "n_flagged_steps": 11
  },
  "context": {
    "states": ["STARVED", "RUN"],
    "buffer_upstream": {"buffer": "B7PB8", "level_t_peak": 24},
    "throughput_dip": true
  }
}
```

### 9.2. RankCause

```json
{
  "alarm_id": "A-2026-021",
  "ranked": [
    {"machine": "B2", "score": 0.91, "edge_id": "B2->B7P"},
    {"machine": "B7P", "score": 0.62, "edge_id": "B7P->B8"},
    {"machine": "B8", "score": 0.41, "edge_id": "B8->B8"}
  ],
  "AC@1": 1,
  "walk_depth": 3,
  "veto_applied": {"ASM2": "2x-margin-rule-checked"},
  "partition": "line-B"
}
```

`ranked` ordered desc by `score`, length ≤3. `AC@1` is 1 when
`ranked[0].machine == fault.origin`. `B8->B8` is the symptom self-edge.
`partition` names the causal partition (§10) the walk ran in.

### 9.3. Explanation

```json
{
  "alarm_id": "A-2026-021",
  "sentences": [
    {
      "text": "Drift of 5.2σ at B2 (t150–t162) exceeds Q_DET=74.6 with peak 77.8.",
      "triple": {
        "fault_window": {"fault_id": "F-21", "t0": 150, "dur": 12},
        "edge_id": "B2->B7P",
        "detector_output": {"machine": "B2", "peak_t": 152, "peak_value": 77.8}
      }
    },
    {
      "text": "B7P BLOCKED (t154–t158, buffer B2B7P level 24/25) then B8 STARVED (t156–t167); degraded parts arrived via flow, no signal copy.",
      "triple": {
        "fault_window": {"fault_id": "F-21", "t0": 150, "dur": 12},
        "edge_id": "B7P->B8",
        "detector_output": {"machine": "B8", "peak_t": 159, "peak_value": 61.4}
      }
    }
  ],
  "grounding_rate": 1.0
}
```

Provenance-id ≡ (fault-window, edge-id, detector-output) triple.
`grounding_rate` = fraction of sentences with a valid resolvable triple;
verifier rejects null/unresolvable triples in rate accounting. `>5%`
ungrounded → chain-cards fallback serves instead (K3), within
NARR_DEADLINE ≤8s. `sentence.triple` is `object|null`.

### 9.4. Replay

```json
{
  "alarm_id": "A-2026-021",
  "seed": 777,
  "fault": "F-21-drift-B2",
  "subgraph": {"nodes": ["B2", "B7P", "B8"], "edges": ["B2->B7P", "B7P->B8"]},
  "partition": "line-B",
  "diverge_bool": false,
  "runs": 5,
  "schema_version": 2,
  "code_version": "twin-2.1.0-topology-A",
  "replay_hash": "sha256:523b0b9e71f47d…"
}
```

Partition-scoped, version-pinned RNG. `runs: 5` same-seed runs,
byte-identical obs on the partition subgraph → `diverge_bool: false`
(K4). `replay_hash` is sha256 over canonical JSONL of the subgraph obs
(canonical payload includes schema_version + code_version, §4.4).

### 9.5. Viva-trail export (one JSON per alarm, SPEC §Viva-trail)

```json
{
  "alarm_id": "A-2026-021",
  "rank_cause": {
    "ranked": [
      {"machine": "B2", "score": 0.91, "edge_id": "B2->B7P"},
      {"machine": "B7P", "score": 0.62, "edge_id": "B7P->B8"},
      {"machine": "B8", "score": 0.41, "edge_id": "B8->B8"}
    ],
    "AC@1_ref": {"battery_run": "topology-A-full182", "AC@1": 0.8125}
  },
  "explanation": {
    "sentences": [
      {"text": "Drift of 5.2σ at B2 (t150–t162) exceeds Q_DET=74.6 with peak 77.8.",
       "triple": {"fault_window": {"fault_id": "F-21", "t0": 150, "dur": 12},
                  "edge_id": "B2->B7P",
                  "detector_output": {"machine": "B2", "peak_t": 152, "peak_value": 77.8}}},
      {"text": "B7P BLOCKED then B8 STARVED via buffer B2B7P; degraded parts arrived via flow.",
       "triple": {"fault_window": {"fault_id": "F-21", "t0": 150, "dur": 12},
                  "edge_id": "B7P->B8",
                  "detector_output": {"machine": "B8", "peak_t": 159, "peak_value": 61.4}}}
    ],
    "grounding_rate": 1.0
  },
  "replay": {"seed": 777, "fault": "F-21-drift-B2",
             "subgraph": {"nodes": ["B2", "B7P", "B8"], "edges": ["B2->B7P", "B7P->B8"]},
             "diverge": false, "runs": 5, "replay_hash": "sha256:523b0b9e71f47d…",
             "schema_version": 2, "code_version": "twin-2.1.0-topology-A"},
  "evidence": {"battery": {"battery_id": "topology-A-full182", "schema_version": 2,
                           "joined_digest": "64af2d24a538d2c7c217b8c244835fe230ec902dccbc8632f0e2b1aa8ddf6cb6",
                           "manifest_rows": 182, "F1": 0.725, "AC@1": 0.8125,
                           "flip_tau2": 0.144, "p99_s": 0.0026},
               "spike_ids": ["battery_rq1_rq2", "closeout"],
               "golden": "services/sim_bridge/golden/replay-777-topology-A.json"}
}
```

Waterfall UI per alarm shows detector output → veto → walk → narration →
replay hash (SPEC FR-4). Detector F1/AC@1/flip figures above are carried
baselines pending MINIPRO-10 re-measurement on the frozen topology-A twin;
twin-side pins (battery_id, digests, manifest rows, schema) are measured.

## 10. Scale and performance budget (battery wall <600s, normative)

PCMCI full-graph on 26 nodes is infeasible on a laptop (conditional
independence tests scale roughly quadratically in node count; detector +
simulation scale linearly). The build therefore partitions:

- Causal partitions (evidence windows, fixed): `line-A`
  (A0,A1,A2,A7,A8,A9), `line-B` (B0,B1,B2,B7P,B7S,B8,B9), `line-C`
  (C0,C1,C2,C6,C7 plus packaging branch PKG0,PKG1,PKG2), `cell` (ASM0,
  ASM1, INSP0, ASM2, RWK0, plus tail inputs A9/B9/C7 as boundary
  conditions). Cross-partition
  edges allowed ONLY at `tails→ASM0` (AGV links) and `ASM2→RWK0→ASM0`
  (rework), evaluated as pairwise boundary checks, never as full-graph
  discovery.
- Per-partition PCMCI caps: ≤10 nodes, `tau_max=2`, N_FLOOR=800 samples
  per partition (downsample channels 1–2 if needed; never channels 6–7).
  Per-partition wall cap 120s; 4 partitions sequential ≤480s, parallel ≤150s.
- Simulation partitioning: one SimPy environment per episode; episodes
  are embarrassingly parallel across seeds. Per-episode obs is
  26 × 300 floats plus sparse events; detector cost is per-machine
  (linear).
- Budget: twin generation + quantile detection + 4 partition PCMCI jobs
  + replay 5× partition-scoped must total <600s wall on the reference
  laptop. If over budget, shed in this order: (1) parallelize partitions,
  (2) downsample channels 1–2 to every 2nd step for PCMCI only,
  (3) shorten T to 250 (never touch CAL_WIN=120). Never shed
  detection/provenance (Kingman SHED_AT per config).

Scaling statement (normative for SDD capacity planning):

- Linear in machine count N: simulation steps, obs storage, quantile
  detection, threshold calibration, replay hashing, event logging.
- Quadratic (or worse) in N: PCMCI conditional-independence tests and
  edge-flip comparisons, hence the partition mandate. Walk cost is
  bounded by WALK_DEPTH × fan-out cap (constant per alarm), not by N.

## 11. Acceptance bars (no softening; regression per TECHNICAL.md §Regression)

`python spike/battery_rq1_rq2.py && python spike/closeout.py` PASS iff
ALL hold: F1 ≥ 0.85 (M0b target; disclose until then) + AC@1 ≥ 70% +
flip < 40% all classes and all partitions + per-fault p99 ≤ 30s + total
wall < 600s + narrative grounding ≥ 95% + same-seed ×5 0-diverge +
vectors green.
Current measured references (32-fault: F1 0.725, AC@1 0.8125) do NOT
lower any bar. Kill-bars: K1 (AC@1<30% or flip>40% → cut learning),
K2 (F1-drop>30pts → quantile mandatory, fired: MP rejected), K3 (>5%
ungrounded → fallback stays), K4 (any diverge → partition-scoped pinned
replay), CAPS ($0.005 / 2.5k tok / iter cap per run).

## 12. REQ-010 coverage checklist (TST-003)

- [x] 26/26 machines + 26/26 buffers + AGV pool (cap 3) + flow/fork/failover/
      packaging/AGV/rework edges simulated per §2–§4 with
      BLOCKING/STARVING/DOWN states (topology-A, schema v2; battery
      `topology-A-full182` green).
- [x] Every machine × every injectable class in §5 injected ≥1: 182-row
      manifest (26×7), coverage zero empty cells, 7 rep pins
      (F-21 B2, F-22 A7, F-23 C2, F-24 B7P, F-25 B2, F-26 B9, F-06 A0).
- [x] T9 duty gates green on seeds [777,1234,999,42,2026]: plant-mean RUN
      share ≥80%, STARVED share ≤15% (24-machine mean, standby scope
      {B7S,RWK0} excluded), BLOCKED reported, xfer_open==0 at T via drain
      accounting (grace 8), pile-up bound held.
- [x] Versioned schema: every battery number carries schema_version=2 +
      battery_id; episode record + replay digest bind schema_version +
      code_version 'twin-2.1.0-topology-A'; v1 32-machine baselines marked
      V1_NON_COMPARABLE, never asserted equal.
- [ ] No `0.45^lag` signal copy anywhere; propagation via WIP/buffers/
      states/part flags only (§4.2 audit note addressed).
- [ ] Data taxonomy §8 fully emitted (channels 1–7 with types/ranges/rates,
      incl. FAILOVER/PACK_FORK/LATE_VERDICT events).
- [ ] Causal evidence partitioned per §10 (no full-26-node PCMCI);
      flip <40% per partition.
- [ ] Battery wall <600s on reference laptop (§10 budget held;
      full182 wall ≈1.3s jobs=12, ≈6.5s jobs=1).
- [ ] Partition-scoped replay context intact: Replay.subgraph + seed +
      partition reproduces the alarm path with 0-diverge (§6, §9.4;
      F-21-on-B2 seed-777 digest `523b0b9e71f47d…`).
- [ ] Viva-trail export per alarm (§9.5) with rank + sentences + triples
      + replay hash + battery numbers.

## Appendix S. Scale-arm reference (32-machine, non-normative until MINIPRO-30 ratifies)

This appendix is non-normative until MINIPRO-30 ratifies. It records the
superseded 32-machine configuration (Lines A/B/C 10/10/8 + ASM0–2 + RWK0,
31 buffers, 224-row manifest, 34-node frontend, flow digest `962b9c54d022`,
demo digest `d2b4fb23…`) for scale-arm comparison only. No normative text
may cite these numbers; exact per-machine coefficients live in git history
prior to the topology-A reshape commits, not here. v1 baselines are
V1_NON_COMPARABLE against schema-v2 numbers by construction (§4.4 digest
binding). MINIPRO-30 owns ratification of any scale-arm claim built on
this appendix.
