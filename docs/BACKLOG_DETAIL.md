# BACKLOG_DETAIL — anomaly-twin-trace (task-level, M0b→M5)

Companion to `docs/BUILD_BACKLOG.md` (scope) + `docs/SPRINT_PACK.md` (stories) + `docs/TEST_PLAN.md` (gates). Owner column uses role placeholders (twin-owner/data-owner/detect-owner/narrate-owner/demo-owner). `spike/` stays quarantine, rewrite-don't-merge: every task that reads spike code writes a new module, never merges spike files. No gate softening. Kill-bar pivots from TEST_PLAN §7 preserved per task.

Gates repeated for traceability: F1≥0.85, AC@1≥70%, flip<40% per partition per class, p99≤3 steps, wall<600s, grounding≥95%, 0-diverge, 32/32 plant coverage (partitions × channels × classes: 7 classes, 7 channels).

## M0b — detector sensitivity (only open bar; do first)

| Task | Files to touch | Acceptance | Dependency | Owner |
|---|---|---|---|---|
| M0b-1 Per-fault sensitivity on F-06/F-12/F-14 | new `src/detect.py` (rewrite from `spike/battery_rq1_rq2.py` Q_DET block); read `spike/trace_battery.jsonl` | Per-fault table (score vs `max(q0.99,Q3+1.5·IQR)`, veto decision, echo overlap) classifies each miss as threshold-shape/feature/cal-window/echo; TC-002 pass | TC-001 baseline run | detect-owner |
| M0b-2 Echo-aware attribution fix | `src/detect.py`, `src/veto.py` (new; VETO_ASM2 logic: ASM2-test needs 2x margin, no other mask) | Battery re-run raw F1≥0.85, F-06/F-12/F-14 recall>0, no regression on other 17; TC-001 pass | M0b-1 | detect-owner |
| M0b-3 AC@1/flip/p99 re-assert | `src/walk.py` (depth≤3/top-k stub), `src/pcmci_job.py` (ParCorr tau2, seeds 7/11/13/17/19, n≥800) | AC@1≥70% + flip<40% per partition per class + p99≤3 reported alongside F1; TC-003/004/005 pass | M0b-2 | detect-owner |
| M0b-4 32/32 plant coverage check | `src/twin.py` (SimPy 32-machine plant: Lines A/B/C 10/10/8 + ASM0–2 + RWK0, gateway buffers + AGV/SBUF, T=300, cal-win 120, SeedSequence) | Full-plant matrix 32/32 machines × 7 classes (spike/drift/bias/delay/loss/breakdown/quality) across partitions × channels, per-partition flip<40%; TC-006 pass | M0b-2 | twin-owner |

Kill-bar: F1 still <0.85 after targeted fix → do NOT lower bar; escalate to detector-comparison study only via parked pivot (K1 must fire first). K2 stays armed (drop>30pts vs quantile → quantile mandatory).

## M1 — detection hardening

| Task | Files to touch | Acceptance | Dependency | Owner |
|---|---|---|---|---|
| M1-1 Versioned quantile-refit artifact + K2 alarm | `src/detect.py` (quantile serialize/version), `src/trail.py` (log quantiles per run) | Refit artifact versioned; >30pts F1 drop vs stored quantile raises alarm; TC-001 re-pass on 32-fault set | M0b | detect-owner |
| M1-2 PCMCI tau-2 evidence job (n≥800 floor) | `src/pcmci_job.py` (pc_alpha=0.05, alpha_level=0.01, cap 120s) | 5-seed flip<40% per partition, lag-stability reported; rejects n<800 windows; TC-003/004 pass | M0b-3 | detect-owner |
| M1-3 Walk depth≤3 + top-k + Kingman-80% shed | `src/walk.py` (fan-out cap 8 per SIM_SPEC §7.3, line-scale fan-out-5 baseline, depth cap, richness-first shed, never detection/provenance) | Depth/top-k enforced; 10x flat-load no OOM; TC-009 V5 pass | M1-2 | detect-owner |
| M1-4 DELAY/LOSS class regression gates | `src/twin.py` (delay d∈[3,6] seed 777; loss 10-30% drops seed 999 + median imputation) | DELAY F1≈0.670 flip 24.2%, LOSS F1≈0.739 flip 30.3%, 32f F1≈0.725 AC@1 0.8125; TC-010 pass | M1-1 | twin-owner |

Kill-bar: any class AC@1<30% or flip>40% → K1 class-pivot (tau≥d evidence window for DELAY; forward-fill/Kalman + wider cal for LOSS), detector unchanged.

## M2 — narration + model wiring

| Task | Files to touch | Acceptance | Dependency | Owner |
|---|---|---|---|---|
| M2-1 Template + verifier + triple gate | `src/narrate.py`, `src/verify.py` (rewrite from `spike/rq3_spike.py`; triple ≡ fault-window/edge-id/detector-output) | Verifier rejects null/unresolvable triples in rate accounting; TC-007 pass at template level | M1 | narrate-owner |
| M2-2 Chain-cards fallback + caps + ≤8s deadline | `src/chaincards.py`, `src/narrate.py` (caps $0.005/2.5k tok/iter) | Deadline breach → 30/30 local cards ≤8s (observed 0.39s), 0 ungrounded pass, 0 egress | M2-1 | narrate-owner |
| M2-3 Gemini/Ollama wiring (topology local-only) + wiring-time grounding | `src/narrate.py` (model adapter; no topology egress) | Wiring-time grounding ≥95% measured or fallback stays armed (K3); 5-hostile probe clean | M2-2 | narrate-owner |

Kill-bar: grounding <95% → K3 fires: cut LLM to chain-cards, ship fallback only.

## M3 — replay + demo harness

| Task | Files to touch | Acceptance | Dependency | Owner |
|---|---|---|---|---|
| M3-1 Subgraph-only replay + SeedSequence | `src/replay.py` (rewrite from `spike/spike_rq4_rq5.py`; version-pinned RNG; whole-flow context preserved) | 5×5 same-seed 0-diverge byte-identical; TC-008 pass | M2 | twin-owner |
| M3-2 20-fault battery regression + <600s assert | `src/twin.py`, harness script (new `scripts/run_battery.py`; NOT spike merge) | 20-fault wall<600s (17.7s line-scale baseline) + p99 reported; TC-009 pass | M3-1 | demo-owner |
| M3-3 Malformed/vacuous/vector gates in harness | harness + `src/trail.py` (log V1-V6 rows) | 10/10 malformed rejected, RSS +0.0%, inverted-label collapse (non-vacuous), 50-coro wall ≈0.015s | M3-2 | demo-owner |

Kill-bar: any diverge → K4 subgraph-only enforced; ROCm/driver sink >1wk → K5 CPU-baseline, no GPU work in window.

## M4 — waterfall UI + viva trail

| Task | Files to touch | Acceptance | Dependency | Owner |
|---|---|---|---|---|
| M4-1 Waterfall UI (EvidencePanel + GraphView patterns) | `src/ui/` (copy patterns from `EvidencePanel.tsx:246` + `GraphView.tsx`; no Jaeger backend, pattern-copy only) | Per-alarm waterfall examiner-clickable with full-plant cause path; TC-011 click path pass | M3 | demo-owner |
| M4-2 Trail export per alarm | `src/trail.py` (battery JSONL → trail: alarm_id, rank_cause, sentences+triples, replay{seed,subgraph,diverge:false,runs:5}, evidence{F1/AC@1/flip/p99,spike_ids}) | Trail per alarm exported; replay hash matches live re-run | M4-1 | data-owner |

Kill-bar: none new; K3/K4 re-checked through UI path (ungrounded sentence or diverged hash visible in trail = block).

## M5 — viva dry-run + calibration

| Task | Files to touch | Acceptance | Dependency | Owner |
|---|---|---|---|---|
| M5-1 KQ close-out + recalibration gate | `src/detect.py`, `src/trail.py` (recal gate per battery run) | KQs answered with numbers (n=800 floor, fan-out cap 8 re-measured at plant scale, Kingman-80%, quantile +60pts over MP); stale-quantile run blocked | M4 | detect-owner |
| M5-2 Dry-run defense of every kill/bar | `docs/` dry-run script (new; no code changes to src) | Defends K1–K5 + F1/AC@1/flip/p99/<600s/≥95%/0-diverge/32/32 with numbers incl. full-plant coverage; TC-011 full pass; pivots trigger-armed, kills unrevived | M5-1 | demo-owner |

| M5-3 Dependency-smoke (pinned stack) | `requirements.txt` pins (simpy/tigramite/networkx/numpy/psutil/scipy per SDD §1) + smoke script | Clean-env install + import + 1-episode twin run green; numpy-version RNG assert recorded in trace | M4 | twin-owner |
| M5-4 Trace-retention pin | `src/trail.py` (retention policy: keep battery JSONL + timing + trail exports per run) | Retention window pinned in trail config; dry-run verifies last N runs replayable from retained traces | M4-2 | data-owner |
| M5-5 Monthly recalibration gate | `src/detect.py`, `src/trail.py` (recal schedule: re-fit quantiles per partition, re-run battery) | Monthly recal run logged with per-partition F1/flip vs stored artifact; drift beyond K2 threshold raises alarm, stale artifact blocks release | M5-1 | detect-owner |

## Parked pivots (add iff trigger; not scheduled)

| Pivot | Trigger | Files if armed |
|---|---|---|
| Minimal-twin fallback + detector-comparison study | K1 fires (AC@1<30%/flip>40%) | `src/twin.py` (reduced), study doc |
| Learned-GDN | flip<20% + drift-spike gain proven | new `src/gdn.py` (torch; CPU-only first) |
| MP-discord | F1≥0.85 + faster/simpler (currently failed: F1 0.063, 1700x slower) | `src/detect_mp.py` |
| Free-LLM narration | ≥95% grounding with margin on wiring-time measurement | `src/narrate.py` adapter swap |
| ROCm GPU | clean driver spike inside 1-wk box | harness config only |

## Killed (no trigger; do not revive without L1 reclassification)

Blind discovery, Rust/Go core, pretrained weights, live stream, fixed thresholds, learned graph, Merlion-as-dependency, Jaeger backend, point-adjusted scoring, Uptake-$160 citation.
