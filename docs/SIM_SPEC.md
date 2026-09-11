# SIM_SPEC — full factory-flow simulation spec, 30+ machine plant (REQ-010, build-ready)

Status: normative for the build twin. A builder implements this file alone,
without reading `spike/`. `spike/` stays quarantine (never merge).
Traceability: REQ-010 (SRS §REQ-010, SDD §2.1/§2.3, TEST_PLAN TST-003).
Measured values carried verbatim from `docs/TECHNICAL.md`,
`docs/ARCHITECTURE.md`, `spike/REPORT_BATTERY.md`, `spike/REPORT_CLOSEOUT.md`.
Bars restated, never softened (§11).

Hand-rolled SimPy only (ADR-0012 rejected FactorySimPy: no trace/fault/RNG
API). Real `simpy.Resource` / `simpy.Store` objects, not abstract delays.

## 1. Scope and non-goals

1.1. This spec defines the entire factory flow twin: 32 machines in 3
parallel lines + assembly cell + rework loop + shared buffer/AGV resource,
mass-flow-conserved propagation, finite buffers with blocking/starving,
per-machine cycle times, breakdown/repair, seeded fault injection with free
ground truth, and the full multi-channel data taxonomy (§8).
1.2. The twin NEVER issues safety-restart clearance (human-only, SPEC FR-9).
1.3. Non-goals (killed, do not rebuild): FactorySimPy twin (REJECTED per
ADR-0012), learned-graph detection, MP-discord detector (F1 0.063, killed),
GDN (torch not importable, skipped), GPU path, live stream, point-adjusted
scoring (inadmissible, never use).

## 2. Plant layout (normative, 32 machines)

2.1. Lines (parallel, independent feeds, join at assembly):

- Line A (10 machines): A0→A1→…→A9, feed raw stock. Roles: feed, form,
  process ×6, finish, inspect.
- Line B (10 machines): B0→B1→…→B9, same role pattern as A.
- Line C (8 machines): C0→C1→…→C7, short line (feed, process ×5, finish,
  inspect).
- Assembly cell (3 machines): ASM0 (kitting from A9/B9/C7), ASM1 (join),
  ASM2 (test). ASM0 pulls one part each from A9, B9, C7 output buffers.
- Rework loop (1 machine): RWK0. ASM2-test rejects route back via
  `ASM2→RWK0→ASM0` buffer path; reworked parts re-enter ASM0 kitting queue.

Total: 10 + 10 + 8 + 3 + 1 = 32 machines.

2.2. Buffers and shared resources:

- Every inter-machine gap has one finite FIFO `simpy.Store` (capacity per
  Table 3.1). 29 line/cell gap buffers + 1 rework return buffer + 1 shared
  overflow buffer = 31 named buffers.
- Shared resource: AGV pool, `simpy.Resource(capacity=2)`. Any transfer
  from a line-tail buffer (A9, B9, C7) to ASM0 kitting must `request()` an
  AGV, hold for `agv_steps` (Table 3.1), then release. AGV queueing is
  logged as wait time per part.
- Shared overflow buffer SBUF (capacity 30, `simpy.Store`): when any
  tail buffer is full, the upstream machine may divert to SBUF only if its
  class allows it (process/finish classes yes; feed/form no). SBUF drains
  to ASM0 when an AGV is free. SBUF occupancy is logged.

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

Machine classes: feed, form, process, finish, inspect, assembly, test,
rework. Cycle times and buffers per class:

| ID | Class | base | σ | cycle_steps | MTTF steps | MTTR steps | Buffer after (cap) | Nominal transit to next |
|---|---|---|---|---|---|---|---|---|
| A0, B0, C0 | feed | 50.0 | 1.0 | 4 | 2000 | 15 | 20 | 2 |
| A1, B1, C1 | form | 60.0 | 1.2 | 5 | 1500 | 12 | 20 | 2 |
| A2–A7, B2–B7, C2–C6 | process | 70.0 | 1.5 | 6 | 800 | 20 | 25 | 3 |
| A8, B8, C7tail* | finish | 55.0 | 1.1 | 4 | 1200 | 10 | 15 | 3 |
| A9, B9 | inspect | 48.0 | 1.4 | 3 | 1500 | 8 | tail 15 | AGV 4–8 |
| C7 | inspect/finish | 48.0 | 1.4 | 3 | 1500 | 8 | tail 15 | AGV 4–8 |
| ASM0 | assembly/kit | 65.0 | 1.3 | 5 | 1000 | 12 | 25 | 2 |
| ASM1 | assembly/join | 66.0 | 1.3 | 6 | 1000 | 12 | 25 | 2 |
| ASM2 | test | 45.0 | 2.0 | 3 | 1200 | 10 | — (sink + rework tap) | — |
| RWK0 | rework | 62.0 | 1.6 | 8 | 900 | 18 | return 10 | 5 |

`*` C7 is the C-line tail inspect machine; its "finish" label is line
shorthand only.

Notes:

- `base`, `σ` fix the clean operating point. Envelope is `base ± 3σ`
  (matches detector §7 on clean data). ASM2 σ=2.0 is the documented
  known-noisy tail; VETO_ASM2 (§7) compensates, do not quiet ASM2 by
  shrinking its σ. VETO rule renamed from VETO_M5 (6-machine era) with
  identical 2×-margin semantics.
- `MTTF/MTTR`: natural breakdowns sampled as geometric per step
  (`p_fail = 1/MTTF` per running step, `p_repair = 1/MTTR` per down step),
  independent of injected faults. State DOWN preempts BLOCKED/STARVED.
  Natural-breakdown steps are flagged in event logs, excluded from fault
  ground-truth windows.
- AGV transit `agv_steps` uniform in [4,8] per trip (sampled on
  `rng_place` stream).
- Every machine × every fault class in its row of §5 must be injected ≥1
  per acceptance battery (TST-003 flow-coverage). Minimum 32 machines ×
  applicable classes; representative-machine shorthand in §5 defines the
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
(≥5-step gap between windows on the same machine).
4.4. Episode record: `{seed, T: 300, cal_win: 120, machines: Table 3.1,
obs[32][300], states[32][300], buffers[31][300], agv_waits[], parts[],
faults[]}`. `faults[]` is free ground truth: `{fault_id, class, origin,
t0, dur, mag_sigma, extra:{d | drop_rate | mttr_mult | reject_rate}}`.

## 5. Fault-injection taxonomy (normative, ≥4 classes × representative machines)

Classes: spike, drift, bias, delay (slow-cycle), loss (drops), breakdown
(extended DOWN), quality (reject-rate). Each row must be injected ≥1 on
each listed representative machine per acceptance battery.

| Class | Mechanism (origin machine) | Params | Representative machines (mandatory) | Downstream observable (via flow, not echo) |
|---|---|---|---|---|
| spike | `+mag·σ` rectangular pulse on origin obs | mag 4–7σ, dur 8–25 | A0(feed), A3(process), B5(process), C2(process), ASM1, RWK0 | degraded part flag travels; brief buffer dip downstream |
| drift | ramp to `mag·σ` on origin obs | mag 4–7σ end, dur 8–25 | A2, B3, C4, ASM0 | growing STARVED gaps downstream as cycle output degrades |
| bias | constant `+mag·σ` on origin obs | mag 4–7σ, dur 8–25 | A4, B6, ASM2 | sustained offset + buffer level shift |
| delay (slow-cycle) | origin `cycle_steps += d`, `d ∈ [3,6]` per step for window | dur 8–25 | A5, B4, C3, ASM0, RWK0 | upstream BLOCKING cascade, downstream STARVING; arrival shift = `nominal + d` per hop |
| loss (drops) | 10–30% observation drops at origin + carried-part flag drops, clean-median imputation before detection (cal intact) | dur 8–25 | A6, B7, C5, ASM1 | thinned signal; flip rises, F1 holds |
| breakdown | force state DOWN for window (`MTTR × mttr_mult`, `mult ∈ [1,3]`) | dur 8–25 | A7, B2, C6, ASM1 | hard BLOCKED upstream + STARVED downstream; throughput zero at origin |
| quality (reject) | ASM2/RWK-path reject rate raised to 15–40% for window | dur 8–25 | ASM2, RWK0, A9, B9 | rework buffer surge, ASM0 kitting starve, throughput dip at sink |

M0-era restriction (delay/loss origins M1+ only, M0 base-classes only) is
superseded: every class above lists its own mandatory origins.

## 6. RNG discipline (normative, K4)

6.1. `SeedSequence` everywhere. Zero bare `default_rng(int)`.
6.2. Per episode with master `seed`:

```
ss = SeedSequence((seed,))
child = ss.spawn(36)  # [AR0..AR31 noise, placement, drops, agv, breakdown]
rng_noise[i] = default_rng(child[i])   # i = 0..31, one stream per machine
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
on the full 32-node graph. PCMCI window floor N_FLOOR=800 (KQ1: 400
unstable, 800 stable). Flip gate <40% per partition.

## 8. Data taxonomy (normative, multi-channel)

Every machine emits channels 1–5 per step; channels 6–7 are plant-level.
Detector thresholds (§7.1) apply to channels 1–2 only.

| # | Channel | Type | Range | Rate | Per machine-class notes |
|---|---|---|---|---|---|
| 1 | vibration/signal `obs` | float | `base ± 6σ` clamp | 1/step | all classes; ASM2 σ=2.0 noisy |
| 2 | temperature | float °C | 20–120 | 1/step | process: 60–95 nominal; feed/form: 20–45; assembly: 25–55; test/rework: 20–60 |
| 3 | throughput/counts | int parts/step | 0–1 (0–3 ASM0 kit) | 1/step | 1 on cycle completion, else 0; DOWN/BLOCKED/STARVED emit 0 |
| 4 | quality flag | enum {OK, DEGRADE, REJECT} | — | per part | inspect/test set REJECT; origin fault sets DEGRADE carried downstream on the part |
| 5 | machine state | enum {RUN, BLOCKED, STARVED, DOWN} | — | 1/step + on-change event | BLOCKED = downstream full; STARVED = upstream empty (ASM0: any kit input empty); DOWN = breakdown |
| 6 | buffer level | int parts | 0–cap | 1/step per buffer (31 buffers) | includes SBUF + rework return buffer |
| 7 | event log | structured `{t, machine, event, detail}` | — | on-change | events: FAULT_START/END, BLOCK_ON/OFF, STARVE_ON/OFF, DOWN/UP, AGV_WAIT, REJECT_ROUTE, DIVERT_SBUF |

Sampling: twin step = 1 sample for channels 1–3, 5–6. Channel 4 sampled
per part completion. Channel 7 is sparse/event-driven. No sub-step
sampling; SDD may downsample channels 1–2 (not 6–7) for PCMCI partitions
under the §10 budget.

## 9. Data contracts and JSON examples (normative keys, types, ranges)

Types: `machine ∈ {A0..A9, B0..B9, C0..C7, ASM0..ASM2, RWK0}`, `t` int step
in `[0,300)`, scores floats in `[0,1]`, `edge_id` string `"X->Y"` (flow
edge, buffer/AGV hops named e.g. `"A9~AGV~ASM0"`, rework `"ASM2~RWK0~ASM0"`).
One running example: fault `F-21` (drift, B5, t0=150, dur=12, mag=5.2σ).

### 9.1. Alarm

```json
{
  "id": "A-2026-021",
  "machine": "B7",
  "t_start": 156,
  "t_end": 167,
  "detector_output": {
    "machine": "B7",
    "channel": "vibration",
    "threshold_qdet": 58.31,
    "peak_value": 61.4,
    "peak_t": 159,
    "n_flagged_steps": 11
  },
  "context": {
    "states": ["STARVED", "RUN"],
    "buffer_upstream": {"buffer": "B56", "level_t_peak": 24},
    "throughput_dip": true
  }
}
```

### 9.2. RankCause

```json
{
  "alarm_id": "A-2026-021",
  "ranked": [
    {"machine": "B5", "score": 0.91, "edge_id": "B5->B6"},
    {"machine": "B6", "score": 0.62, "edge_id": "B6->B7"},
    {"machine": "B7", "score": 0.41, "edge_id": "B7->B7"}
  ],
  "AC@1": 1,
  "walk_depth": 3,
  "veto_applied": {"ASM2": "2x-margin-rule-checked"},
  "partition": "line-B"
}
```

`ranked` ordered desc by `score`, length ≤3. `AC@1` is 1 when
`ranked[0].machine == fault.origin`. `B7->B7` is the symptom self-edge.
`partition` names the causal partition (§10) the walk ran in.

### 9.3. Explanation

```json
{
  "alarm_id": "A-2026-021",
  "sentences": [
    {
      "text": "Drift of 5.2σ at B5 (t150–t162) exceeds Q_DET=74.6 with peak 77.8.",
      "triple": {
        "fault_window": {"fault_id": "F-21", "t0": 150, "dur": 12},
        "edge_id": "B5->B6",
        "detector_output": {"machine": "B5", "peak_t": 152, "peak_value": 77.8}
      }
    },
    {
      "text": "B6 BLOCKED (t154–t158, buffer B56 level 24/25) then B7 STARVED (t156–t167); degraded parts arrived via flow, no signal copy.",
      "triple": {
        "fault_window": {"fault_id": "F-21", "t0": 150, "dur": 12},
        "edge_id": "B6->B7",
        "detector_output": {"machine": "B7", "peak_t": 159, "peak_value": 61.4}
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
  "subgraph": {"nodes": ["B5", "B6", "B7"], "edges": ["B5->B6", "B6->B7"]},
  "partition": "line-B",
  "diverge_bool": false,
  "runs": 5,
  "code_version": "twin-2.0.0",
  "replay_hash": "sha256:9f2c…e1"
}
```

Partition-scoped, version-pinned RNG. `runs: 5` same-seed runs,
byte-identical obs on the partition subgraph → `diverge_bool: false`
(K4). `replay_hash` is sha256 over canonical JSONL of the subgraph obs.

### 9.5. Viva-trail export (one JSON per alarm, SPEC §Viva-trail)

```json
{
  "alarm_id": "A-2026-021",
  "rank_cause": {
    "ranked": [
      {"machine": "B5", "score": 0.91, "edge_id": "B5->B6"},
      {"machine": "B6", "score": 0.62, "edge_id": "B6->B7"},
      {"machine": "B7", "score": 0.41, "edge_id": "B7->B7"}
    ],
    "AC@1_ref": {"battery_run": "closeout-32f", "AC@1": 0.8125}
  },
  "explanation": {
    "sentences": [
      {"text": "Drift of 5.2σ at B5 (t150–t162) exceeds Q_DET=74.6 with peak 77.8.",
       "triple": {"fault_window": {"fault_id": "F-21", "t0": 150, "dur": 12},
                  "edge_id": "B5->B6",
                  "detector_output": {"machine": "B5", "peak_t": 152, "peak_value": 77.8}}},
      {"text": "B6 BLOCKED then B7 STARVED via buffer B56; degraded parts arrived via flow.",
       "triple": {"fault_window": {"fault_id": "F-21", "t0": 150, "dur": 12},
                  "edge_id": "B6->B7",
                  "detector_output": {"machine": "B7", "peak_t": 159, "peak_value": 61.4}}}
    ],
    "grounding_rate": 1.0
  },
  "replay": {"seed": 777, "subgraph": {"nodes": ["B5", "B6", "B7"], "edges": ["B5->B6", "B6->B7"]},
             "diverge": false, "runs": 5, "replay_hash": "sha256:9f2c…e1"},
  "evidence": {"battery": {"F1": 0.725, "AC@1": 0.8125, "flip_tau2": 0.144, "p99_s": 0.0026},
               "spike_ids": ["battery_rq1_rq2", "closeout"]}
}
```

Waterfall UI per alarm shows detector output → veto → walk → narration →
replay hash (SPEC FR-4).

## 10. Scale and performance budget (battery wall <600s, normative)

PCMCI full-graph on 32 nodes is infeasible on a laptop (conditional
independence tests scale roughly quadratically in node count; detector +
simulation scale linearly). The build therefore partitions:

- Causal partitions (evidence windows, fixed): `line-A` (A0–A9),
  `line-B` (B0–B9), `line-C` (C0–C7), `cell` (ASM0, ASM1, ASM2, RWK0,
  plus tail inputs A9/B9/C7 as boundary conditions). Cross-partition
  edges allowed ONLY at `tails→ASM0` (AGV links) and `ASM2→RWK0→ASM0`
  (rework), evaluated as pairwise boundary checks, never as full-graph
  discovery.
- Per-partition PCMCI caps: ≤10 nodes, `tau_max=2`, N_FLOOR=800 samples
  per partition (downsample channels 1–2 if needed; never channels 6–7).
  Per-partition wall cap 120s; 4 partitions sequential ≤480s, parallel ≤150s.
- Simulation partitioning: one SimPy environment per episode; episodes
  are embarrassingly parallel across seeds. Per-episode obs is
  32 × 300 floats plus sparse events; detector cost is per-machine
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

- [ ] 32/32 machines + 31/31 buffers + AGV pool + flow/AGV/rework edges
      simulated per §2–§4 with BLOCKING/STARVING/DOWN states.
- [ ] Every machine × every injectable class in §5 injected ≥1
      (representative-machine subset mandatory, full cross product target).
- [ ] No `0.45^lag` signal copy anywhere; propagation via WIP/buffers/
      states/part flags only (§4.2 audit note addressed).
- [ ] Data taxonomy §8 fully emitted (channels 1–7 with types/ranges/rates).
- [ ] Causal evidence partitioned per §10 (no full-32-node PCMCI);
      flip <40% per partition.
- [ ] Battery wall <600s on reference laptop (§10 budget held).
- [ ] Partition-scoped replay context intact: Replay.subgraph + seed +
      partition reproduces the alarm path with 0-diverge (§6, §9.4).
- [ ] Viva-trail export per alarm (§9.5) with rank + sentences + triples
      + replay hash + battery numbers.
