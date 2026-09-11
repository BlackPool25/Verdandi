<!-- ELENCHUS_HANDOFF_PAYLOAD_V1 -->
# Elenchus Problem Discovery Brief: anomaly-twin-trace
## 1. Validated Problem Statement & Target Persona
POV: BTech student team (semester demo, viva-graded) needs ranked causal trace + why-explanation for every factory-twin alarm because detectors alone force 30-60min hand-triage and unverifiable stories lose marks.
Persona: 2-4 person team, 12-14 weeks, AI-assisted coding, AMD 7900GRE ROCm (1-week timebox, else CPU fallback), Python-first + FactorySimPy, Gemini API (Ollama fallback, topology local-only). When: fault-injection demo + viva defense. Where-findable: teammates + professor + lab; 10-findable path = seniors on IoT/ICS projects + Grafana-rule hackers.
Taken-for-granted: "AI coding makes 4 layers cheap to keep all" — unproven; integration + calibration dominate (kept per human pick, guarded by K1-K5).
Stakeholders: users = student team + operators; economic buyers = professor (marks); blockers = lab infra / ROCm drivers; saboteurs = topology-drift + hallucinated-blame (trust burn). System-in-action: WhatsApp HMI photo + senior gut (20min/stop), Excel logs, Grafana hand-rules. Do-not-digitalize: final safety-restart decision stays human; twin never issues clearance. Coverage: users×interview/workaround-costing ✓; buyers×workshop (viva dry-run) → Crucible; blockers×observation ✓; saboteurs×assumption-test → RQ2/RQ3.
SISP: PASS — plain-words problem (which upstream machine caused it), NOW-who (team needing audit trail for viva + hackers wanting attribution), insight (topology-prior + free sim replay inverts prod economics).
HMWs: HMW rank upstream causes in <3 steps so fix hits root not symptom? HMW make every flag viva-defensible with replay evidence? HMW keep full-twin demo <10min on one laptop without ROCm sink? (scope check: each admits 5-min probe — seed-sweep / provenance-count / timed-run — and 5-yr win = trustworthy industrial RCA pattern.)
## 2. Solved-Shape Metrics & Non-Functional Constraints
Human-pinned STRICT bar (ship thresholds): detection F1>=0.85 (direction: up), trace AC@1>=70% @20 injected faults (up), detection latency<=3 timesteps (down), end-to-end demo<10min on team GRE/laptop (down), explanation groundedness>=95% sentences with provenance id (up).
Elicitation metrics: tacit-probe yield 3/interview (ROCm trap, false-why>silence, replay determinism) >=2 ✓; observation-grounding >=1/opportunity ✓ (J1-J4 cite 2026 reports); Ulwick human-rated: cause-ranking I10/S1→19, viva-trail I9/S1→17 (ship>=10 ✓✓); assumption coverage 100% top-3 ✓ (§3).
NFR: local-first topology, Gemini narration only (no layout egress), machine-only anonymized traces, no safety-clearance claims, deterministic seeded replay.
## 3. Killer Assumptions (To Be Spiked by Crucible)
| Solution | Assumption (<=25 words) | Importance | Evidence |
|---|---|---|---|
| GDN + topology-prior detector | Skeleton stays correct all semester | High | None — needs drift test |
| Constrained PCMCI lags/weights | Short runs yield stable lags, not spurious | High | None — needs seed-sweep |
| Template+verifier LLM narration | Provenance grounding holds >=95% sentences | High | TAMO-FoA/KRCA patterns |
Riskiest Assumption Test: 20-fault injection battery, topology-masked PCMCI across 5 seeds; PASS if AC@1>=70% + edge-flip<40% + F1>=0.85; KILL (<30% AC@1 or flip>40%) → pivot to minimal-twin fallback (stats+topology+chain-cards).
To Be Spiked: topology-drift → RQ1 veto-mask spike; PCMCI stability → RQ2 lag-sweep; narration grounding → RQ3 template+verifier; replay determinism → RQ4 seeded subgraph replay; ROCm/perf → RQ5 CPU-fallback timing.
Outcome tree: Outcome = viva-defensible trace (AC@1>=70%, <10min) → Opp A cause-ranking (GDN vs stats) → Opp B auditability (provenance narration) → Opp C safe fault-demo (subgraph replay); sketches map 1:1 to rows above, each with cheapest falsifying test + pivot bar.
## 4. Graveyard Autopsy (Past Failures & 10x Shift Proof)
Precedents: GE Predix $4-7B burn/selloff (friction+distribution) [Tier3]; Uptake $2.3B→~160 (inverted economics) [Tier3]; Twitter-AD archived 2021 (friction) [Tier2]; EGADS stale (premature) [Tier2]; TensorZero archived Jun2026 (distribution) [Tier3]; $47K agent loop (no caps) [Tier2]. Negatives: GAD-in-wild OOM 500k-1M [Tier2]; TCN-GAT SWaT 0.886→0.281 collapse [Tier1 IEEE].
10x: NO 10x for prod twin upkeep (linear in services) → KILL prod framing; NO 10x raw GNN scale → KILL scale framing; PASS guardrailed LLM-RCA only (cache+routing+filter+caps >10x $/incident <$0.50 <60s; TAMO-FoA 76.3% -34%MTTR + KRCA -77.3% time, two-domain Tier1/2). Semester inversion: sim ownership zeroes upkeep + free ground truth/replay — Predix logic NOT transferred; threshold fragility + hallucination DO transfer → strict bars + verifier mandatory.
## 5. Non-Negotiable Falsification / Kill Criteria
K1 causal unstable (AC@1<30% @20 faults / flip>40%) → cut learning, keep topology+stats. K2 threshold collapse (F1 drop>30pts fixed→adaptive) → per-machine quantile mandatory. K3 ungrounded (>5% sans provenance) → cut LLM to chain-cards. K4 nondeterministic replay (same-seed diverge) → subgraph-only replay. K5 ROCm sink (>1wk) → CPU-baseline + GPU-only GNN.
| Pick | Kill criterion | Crucible RQ | Spike target |
|---|---|---|---|
| Full twin-trace (PICKED) | K1+K2 strict bars | RQ1/RQ2 detector+causal | 20-fault battery + sweep |
| Full explanation trusted | K3 95% provenance | RQ3 narration | template+verifier pipe |
| Full demo survives | K4+K5 time/determinism | RQ4/RQ5 replay+perf | seeded <10min run |
Deferred (not killed): minimal-twin fallback + detector-comparison study — parked as pivots if K1/K3 fire. Killed: blind-discovery twin, Rust/Go core sim, pretrained-weight reuse, live-streaming (rationale: fragile / thin DES ecosystem / topology-specific / batch suffices).
Reuse: FactorySimPy graph twin, PyRCA walk patterns (watch exponential), Merlion DefaultDetector (/salesforce/merlion) baseline glue, RCAEval AC@K harness, Jaeger-waterfall UI, triage-tag fallback. Skipped: Rust/Go core, blind discovery, pretrained weights, live stream (see kills).
Commitment: cheapest proof = 20-fault injection demo battery (ground truth free in sim) → then fresh-chat /crucible.
<!-- END_ELENCHUS_HANDOFF -->
