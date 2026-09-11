# PROBLEM — what we solve, for whom, and what Elenchus found (expanded from `ELENCHUS_DISCOVERY.md`)

Source: Elenchus V1 payload (`<!-- ELENCHUS_HANDOFF_PAYLOAD_V1 -->`, slug anomaly-twin-trace). This file
explains it in plain words; the brief stays byte-exact as the authority. V1→Crucible traceability at the end.

## Plain-words problem
Factory-twin alarms fire, but detectors only say *something is wrong*. The team hand-triages every flag for
30–60 minutes and defends unverifiable stories in viva. Needed: for EVERY alarm, the ranked upstream machine
that caused it (≤3 steps from symptom) plus a why-explanation with replay evidence behind each sentence.

## POV + persona
POV: BTech student team (semester demo, viva-graded) needs ranked causal trace + why-explanation per alarm
because detectors alone force hand-triage and unverifiable stories lose marks.
Persona: 2–4 people, 12–14 weeks, AI-assisted coding; AMD 7900GRE ROCm (1-week timebox, else CPU fallback);
Python-first + FactorySimPy; Gemini API (Ollama fallback, topology local-only). Moment: fault-injection demo +
viva defense. Findable help: teammates + professor + lab; 10-findable path = seniors on IoT/ICS projects +
Grafana-rule hackers. Taken-for-granted (flagged unproven, guarded by K1–K5): "AI coding makes 4 layers cheap."

## Status quo (system in action)
WhatsApp HMI photo + senior gut (20 min/stop), Excel logs, Grafana hand-rules.
Do-not-digitalize: final safety-restart decision stays human — the twin NEVER issues clearance.

## Stakeholders + coverage
Users: student team + operators · Buyers (marks): professor · Blockers: lab infra / ROCm drivers (observed) ·
Saboteurs: topology-drift + hallucinated-blame (assumption-tested → RQ2/RQ3). Coverage: users×interview +
workaround-costing ✓ · buyers×workshop (viva dry-run → Crucible) · blockers×observation ✓ ·
saboteurs×assumption-test ✓. SISP: PASS (plain problem, NOW-who, topology-prior + free-sim-replay insight).

## HMWs (each admits a 5-min probe; 5-yr win = trustworthy industrial RCA pattern)
1. Rank upstream causes in <3 steps so the fix hits root, not symptom? (probe: seed-sweep)
2. Make every flag viva-defensible with replay evidence? (probe: provenance-count)
3. Keep full-twin demo <10min on one laptop without ROCm sink? (probe: timed-run)

## Solved shape (human-pinned STRICT bars — ship thresholds, direction matters)
| Metric | Bar | Direction | Crucible outcome |
|---|---|---|---|
| Detection F1 | ≥0.85 | up | ~0.73 CONDITIONAL → M0b |
| Trace AC@1 @20 faults | ≥70% | up | 0.80–0.8125 PROVEN |
| Detection latency | ≤3 timesteps | down | p99 ≤3.8ms PROVEN |
| End-to-end demo | <10min, team GRE/laptop | down | 17.7s PROVEN |
| Grounding | ≥95% sentences w/ provenance id | up | 1.00 template-proven; LLM → M2 |
Elicitation: tacit-probe yield 3/interview (ROCm trap, false-why>silence, replay determinism) ·
observation-grounding ≥1/opportunity (J1–J4 cite 2026 reports) · Ulwick cause-ranking 19, viva-trail 17
(ship≥10 ✓✓) · top-3 assumption coverage 100%.
NFRs: local-first topology · Gemini narration only (no layout egress) · anonymized machine traces ·
no safety-clearance claims · deterministic seeded replay.

## Killer assumptions (Elenchus rows → Crucible RQs → verdicts)
| Assumption (≤25w) | Evidence then | Became | Verdict now |
|---|---|---|---|
| Skeleton stays correct all semester | none — drift test | RQ1 | FIXED mask stands; flip-gated |
| Short runs yield stable lags, not spurious | none — seed-sweep | RQ2 | flip 14.4%, n≥800 |
| Provenance grounding holds ≥95% | TAMO-FoA/KRCA patterns | RQ3 | 1.00 template; LLM open |
| (+ added in spikes) replay determinism | — | RQ4 | 0-diverge |
| (+ added) ROCm/perf fit | — | RQ5 | CPU-only, ROCm killed |
Riskiest-assumption test: 20-fault battery, topology-masked PCMCI ×5 seeds; PASS AC@1≥70% + flip<40% +
F1≥0.85 (2/3 → CONDITIONAL, no pivot). Outcome tree: viva-defensible trace → cause-ranking (GDN vs stats) →
auditability (provenance narration) → safe fault-demo (subgraph replay), each with falsifying test + pivot bar.

## Graveyard (past failures → what transfers; full narratives in `docs/RESEARCH.md`)
GE Predix $4–7B burn/selloff (friction+distribution) · Uptake $2.3B→~stall (inverted economics) ·
Twitter-AD archived 2021 (friction) · EGADS stale (premature) · TensorZero archived Jun-2026 (distribution) ·
$47K agent loop (no caps → caps mandatory) [Tiers 2–3] · GAD-in-wild OOM 500k–1M [Tier2] ·
TCN-GAT SWaT 0.886→0.281 collapse [Tier1 IEEE].
10x test: NO 10x for prod upkeep (linear) → prod framing KILLED · NO 10x raw GNN scale → scale framing
 KILLED · PASS guardrailed LLM-RCA only (cache+routing+filter+caps >10× $/incident <$0.50 <60s; TAMO-FoA
76.3% −34%MTTR + KRCA −77.3%, two-domain Tier1/2 — cited papers' fleet-level figures, not project claims; our bar is per-alarm: 30–60min hand-triage → ranked cause + replay in seconds). Semester inversion: sim ownership zeroes upkeep + free
ground truth/replay (Predix logic NOT transferred); threshold fragility + hallucination DO transfer
(strict bars + verifier mandatory).

## Picks, pivots, kills (K1–K5 in README; bars reused as-is, never redefined)
PICKED: full twin-trace (K1+K2 bars → RQ1/RQ2 battery) · full explanation trusted (K3 → RQ3 pipe) ·
full demo survives (K4+K5 → seeded <10min run). DEFERRED (parked pivots): minimal-twin fallback +
detector-comparison study (fire iff K1/K3). KILLED: blind-discovery twin · Rust/Go core sim ·
pretrained-weight reuse · live-streaming (fragile / thin DES / topology-specific / batch suffices).
Reuse: FactorySimPy graph twin (→ hand-rolled, ADR-0012) · PyRCA walk patterns (capped) · Merlion
DefaultDetector glue (archived dep, never load-bearing) · RCAEval AC@K harness · Jaeger-waterfall UI
(pattern only) · triage-tag fallback.

## How Elenchus derived this (method, so builders trust the brief)
Coverage matrix (users/buyers/blockers/saboteurs × interview/workshop/observation/assumption-test) ·
tacit probes (yield 3/interview) · observation grounding (J1–J4, 2026 reports) · Ulwick human rating ·
assumption-coverage audit (100% top-3) · graveyard autopsy with 10x-shift proof · cheapest-proof commitment:
the 20-fault battery (ground truth free in sim) → fresh-chat `/crucible` (this dossier).

## V1 → dossier traceability (zero-redundancy: pinned verbatim, never re-elicited)
| V1 § | Landed in |
|---|---|
| §1 problem/persona/stakeholders/HMWs | PROBLEM.md (this file) + invariants (BLACKBOARD) |
| §2 metrics/NFRs | README bars + SCORECARD + SPEC FR-1–FR-9 |
| §3 assumptions + RAT + outcome tree | RQ1–RQ5 → spikes (SPIKES.md) + RESEARCH.md |
| §4 graveyard + 10x | RESEARCH.md + SCORECARD Q15 |
| §5 kills/picks/reuse + commitment | DECISIONS ADR-0001–0012 + BUILD_BACKLOG + battery |
