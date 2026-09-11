# SRS: anomaly-twin-trace (IEEE 29148)

## 1 Purpose
This SRS specifies the viva-defensible causal-twin for factory alarms. Readers: student builders, professor/examiner, lab infra. V1-§1 COPY: BTech student team (semester demo, viva-graded) needs ranked causal trace + why-explanation for every factory-twin alarm because detectors alone force 30-60min hand-triage and unverifiable stories lose marks.

## 2 Scope
In: full 32-machine factory-flow simulation (Lines A/B/C 10/10/8 + assembly cell ASM0–2 + rework RWK0, gateway buffers + AGV pool + shared overflow buffer, mass-flow-conserved propagation, partitioned causal evidence per SIM_SPEC §§2/10), seeded fault injection, detection, topology-constrained trace (depth ≤3 intra-partition + 1 gateway hop), provenance-gated narration, seeded replay, waterfall UI, viva-trail export, <10min CPU demo. Out: safety-restart clearance (human-only, never issued by twin); live-streaming; prod upkeep. V1-§1 problem copied: detectors alone force hand-triage; every flag must be viva-defensible with replay evidence.

## 3 Product perspective
Local-first Python twin (SimPy, networkx) on one CPU laptop; Gemini narration only (no layout egress, Ollama fallback, topology local-only); machine-only anonymized traces; Jaeger-waterfall UI patterns. Interfaces: seeded fault injector → detector → veto → walk → narrate/verify → replay → export.

## 4 Product functions
Rank upstream causes; explain with provenance triples or chain-cards fallback; deterministic replay of the full flow; waterfall view; one-export viva trail; <10min demo; graceful degrade; capped runs; no safety authority. Detail in §8.

## 5 User characteristics
- STK-001 student team (2-4, 12-14 wks, AI-assisted, Python-first): runs twin, injects faults, defends viva.
- STK-002 professor/examiner (buyer, marks): probes any alarm live, needs replay + per-sentence provenance.
- STK-003 lab infra (blocker): provides CPU laptop, no GPU/network trust.

## 6 Constraints and limitations
Local-first topology; Gemini narration only; anonymized machine traces; no safety-clearance claims; deterministic seeded replay; CPU-only demo <10min; ROCm 1-week timebox else CPU fallback.

## 7 Assumptions and dependencies
- ASSUMED: Skeleton stays correct all semester (V1-§3, unspiked — needs drift test).
- ASSUMED: Short runs yield stable lags, not spurious (V1-§3, unspiked — needs seed-sweep).
- ASSUMED: Provenance grounding holds >=95% sentences (V1-§3, unspiked — TAMO-FoA/KRCA patterns only).
- Depends on: FactorySimPy graph patterns, PyRCA walk, Merlion DefaultDetector glue, RCAEval AC@K harness.

## 8 Specified requirements
### 8.1 Functions
- `REQ-001 system shall return ranked upstream causes within depth <=3 steps for every alarm with AC@1>=70% @20 faults source: V1-§2 priority: High`
- `REQ-002 system shall attach provenance triple (fault-window, edge-id, detector-output) to >=95% explanation sentences else serve chain-cards source: V1-§2 priority: High`
- `REQ-003 system shall replay any alarm from seed+subgraph with zero divergence across repeated runs source: V1-§2 priority: High`
- `REQ-010 system shall simulate the entire factory flow (all 32 machines: Lines A/B/C 10/10/8 + ASM0–2 + RWK0, mass-flow-conserved flow via gateway buffers + AGV/SBUF, 31 buffers, per-machine operating envelope, per-partition causal evidence with P≈6–8 nodes) so every alarm is attributable to a full-plant causal path, not an isolated machine source: SPEC+ARCHITECTURE priority: High`

### 8.2 External interfaces
- `REQ-004 system shall render per-alarm waterfall (detector output, veto, walk, narration, replay hash) source: V1-§1 priority: Med`
- `REQ-005 system shall export one viva trail per alarm (rank, sentences, triples, replay hash, battery numbers) source: V1-§1 priority: Med`

### 8.3 Usability requirements
Waterfall + export readable by examiner in viva (spot-check 3 triples, replay ×2 live).

### 8.4 Performance requirements (V1-§2 metrics copied verbatim)
V1-§2 STRICT bar verbatim: detection F1>=0.85 (direction: up), trace AC@1>=70% @20 injected faults (up), detection latency<=3 timesteps (down), end-to-end demo<10min on team GRE/laptop (down), explanation groundedness>=95% sentences with provenance id (up).
- `REQ-006 system shall complete end-to-end demo in <10min on CPU laptop source: V1-§2 priority: High`
- `REQ-007 system shall serve 100% of narration requests via local fallback within <=8s on model tail and shed richness before provenance under 10x ingress source: V1-§5 priority: Med`

### 8.5 Logical database requirements
Single-record JSONL traces per run (trace_battery/m0/closeout/rq3 + traces/timing.json); schemas per SPEC export.

### 8.6 System attributes
- `REQ-008 system shall bound every run by token/USD/iteration caps source: V1-§4 priority: Med`
- `REQ-009 system shall NEVER issue safety-restart clearance source: V1-§1 priority: High`

## 9 Verification
- REQ-001: test 20-fault battery, AC@1>=70%, depth audit.
- REQ-002: inspection of triple-gate log, grounding rate>=95%.
- REQ-003: test same-seed ×2 replay, diverge=false.
- REQ-004: demo examiner-picked alarm renders all 5 stages.
- REQ-005: inspection JSON export schema completeness.
- REQ-006: test timed CPU run <600s (battery 17.7s line-scale baseline + narration ≤60s).
- REQ-007: test kill-model-call → chain-cards ≤8s, 100% served.
- REQ-008: analysis cap-enforcement log per run.
- REQ-009: inspection + test no clearance string/path exists.
- REQ-010: inspection full-plant topology (32/32 machines + flow/gateway edges + 31 buffers + AGV pool) + fault-injection coverage per partition × channel × class (7 classes, 7 channels, per-partition flip<40%) + partition-scoped replay preserves alarm-path context.

## 10 Appendices
- derived-appendix: from V1-§5 — K1 causal unstable (AC@1<30%/flip>40%) → cut learning, keep topology+stats.
- derived-appendix: from V1-§5 — K2 threshold collapse (F1 drop>30pts) → per-machine quantile mandatory.
- derived-appendix: from V1-§5 — K3 ungrounded (>5% sans provenance) → cut LLM to chain-cards.
- derived-appendix: from V1-§5 — K4 nondeterministic replay (same-seed diverge) → subgraph-only replay.
- derived-appendix: from V1-§5 — K5 ROCm sink (>1wk) → CPU-baseline + GPU-only GNN.
- Note: measured 32-fault F1 0.725 AC@1 0.8125 CONDITIONAL GO, M0b sensitivity first.
- Acronyms: AC@1 top-1 causal accuracy; PCMCI causal discovery; GDN graph deviation network.

## A Accept checklist
1. Necessary — each REQ ties to viva/rank/provenance/full-flow value. 2. Appropriate — no design beyond need; spike/ quarantine rewrite-not-merge. 3. Unambiguous — two readers paraphrase each shall identically. 4. Complete — FR-1–FR-9 + V1 metrics covered. 5. Singular — one requirement per ID. 6. Feasible — CPU-only stack pinned; battery 17.7s line-scale baseline. 7. Verifiable — pass/fail per §9. 8. Correct — confirmed vs V1 + SPEC. 9. Conforming — every REQ has ID, shall, source, priority, metric.
