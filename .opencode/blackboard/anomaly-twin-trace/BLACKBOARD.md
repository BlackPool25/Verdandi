# anomaly-twin-trace — Phase: DONE (approved-gate pending)

## Pinned Invariants (Immune to Compaction)
- NEVER: twin issues safety-restart clearance — final restart stays human.
- NEVER: accept vendor marketing / blogs (Tier 4/5) as proof — load-bearing needs Tier 1–3 + 2-domain corroboration or spike.
- NEVER: merge spike/ code to production; spikes quarantined in spike/.
- NEVER: vote on empirical truths — resolve by evidence or spike (Wieringa gate).
- NEVER: build without approved PLAN.md (PR/FAQ + RFC + ADRs + scorecard filed).
- MUST: detection F1>=0.85, trace AC@1>=70% @20 faults, latency<=3 steps, demo<10min one laptop, grounding>=95% sentences w/ provenance id.
- MUST: local-first topology, Gemini narration only (no layout egress), anonymized machine traces, deterministic seeded replay.
- MUST: K1–K5 kill bars enforced (K1 AC@1<30%/flip>40%→cut learning; K2 F1 drop>30pts→per-machine quantile; K3 >5% sans provenance→chain-cards; K4 diverge→subgraph-only; K5 ROCm>1wk→CPU-baseline).

## Goal (1 Line)
Viva-defensible ranked causal trace + why-explanation for every factory-twin alarm in <10min on one laptop.

## Active Epistemic Claims — ALL CLOSED
- [x] K1 SURVIVE global + per-class ×5 (base/DELAY/LOSS × flip) — no pivot (ADR-0009/0012)
- [x] K2 FIRES → quantile mandatory; MP REJECTED; learning-detection CUT
- [x] K3/K4/K5 SURVIVE (ADR-0007/0008)
- [x] M0 echo KILLED honestly (ceiling ≈0.76; ADR-0011) → M0b sensitivity build item
- [x] Close-out: blind-spot NOT reproduced; FactorySimPy KEEP-HANDROLLED (ADR-0012)
- [x] Filed: PR/FAQ + RFC + scorecard (D-L4/V-L3/F-L3) + PLAN.md + 2 addenda; zero known pre-build holes

## Blockers
- Plan approval — final gate (user).

## Single Next Action
- User approves → HANDOFF populated → $start-work (M0b sensitivity first). No build before approval.

## HANDOFF
- Root ~/projects/anomaly-twin-trace/ · Brief ELENCHUS_DISCOVERY.md · Memory .opencode/blackboard/anomaly-twin-trace/ · Docs docs/PR_FAQ.md docs/RFC.md docs/SCORECARD.md · Plan PLAN.md · Spikes spike/ (battery, RQ3, RQ4/RQ5, M0, closeout + JSONL traces) · Gates K1–K5 + M0b bar.
