# PLAN.md — anomaly-twin-trace (Crucible-gated, approval required)

## Verified goal (1 line)
Viva-defensible ranked causal trace + why-explanation per factory-twin alarm in <10min on one CPU laptop (battery: AC@1 80%, 17.7s total, p99 3.7ms/fault).

## Build order (riskiest first)
- **M0 echo-aware attribution → F1≥0.85.** Suppress downstream-echo FPs inside PCMCI lag window; re-run 20-fault battery; PASS F1≥0.85 + AC@1≥70% + flip<40%. (Only open bar; no new infra.)
- **M1 detection path hardening.** Versioned quantile-refit artifact + K2 drop>30pts alarm; PCMCI tau=2 evidence job (n≥800 floor); walk depth≤3 + top-k.
- **M2 narration + model wiring.** Template+verifier + chain-cards + caps; Gemini/Ollama wiring; wiring-time grounding measurement (K3 gate: >5% ungrounded → fallback stays).
- **M3 replay + demo harness.** Subgraph-only replay, 5× same-seed 0-diverge gate; 20-fault battery as regression gate; <600s budget assert.
- **M4 waterfall UI + viva trail.** Copy EvidencePanel/GraphView patterns; battery JSONL → viva-trail export.
- **M5 viva dry-run + calibration.** KQ close-out (n=800, fan-out-5, 80%-knee); recalibration gate per battery.

## Stack & patterns (EVIDENCE-cited)
SimPy 4.1.2 + networkx twin; per-machine quantile/IQR + fixed veto-mask (K2-mandated; MP-discord rejected F1 0.063); tigramite PCMCI evidence-only (flip 14.4%); template+verifier narration (grounded 1.00 harness); SeedSequence replay (0-diverge); CPU-only (ROCm killed).

## In-repo reuse (not reinvented)
FactorySimPy graph-twin pattern; RCAEval AC@K harness shape; Merlion DefaultDetector glue idea (never the archived dep); EvidencePanel.tsx:246 + GraphView.tsx waterfall (sih26146-bitcoin-prototype); triage-tag chain-cards fallback.

## Deliberately skipped (+ trigger to add)
Learned-GDN (add iff flip<20% + drift-spike gain); MP-discord detector (add iff F1≥0.85 + faster/simpler — failed both); free-LLM narration (add iff ≥95% grounding with margin); ROCm GPU (add iff clean driver spike in 1-wk box); live-stream/blind-discovery/pretrained/Rust-Go (no trigger — killed).

## Acceptance criteria per milestone
M0: battery F1≥0.85 (raw), AC@1≥70%, flip<40%. M1: refit-versioned + K2 alarm live. M2: grounding≥95% or fallback armed + caps enforced. M3: 0-diverge + <600s. M4: trail exports per alarm. M5: dry-run viva defensible end-to-end.

## Momus-style self-review
Clarity: every MUST carries a number + gate (F1/AC@1/flip/p99/<600s/95%/8s/caps). Completeness: all C1–C6 closed or gated (C2/C3 battery-resolved-conditional; full-LLM grounding explicitly deferred to M2 with armed fallback). Verifiability: each milestone ends in a battery/spike re-run, not a demo narrative. Risk: F1-precision is the single load-bearing unknown — sequenced first (M0), pivot (minimal-twin) parked but unneeded (K1 survives).

## HANDOFF (build engine entry)
- Root: ~/projects/anomaly-twin-trace/ · Brief: ELENCHUS_DISCOVERY.md · Memory: .opencode/blackboard/anomaly-twin-trace/ (BLACKBOARD/EVIDENCE/DECISIONS/contradictions-map) · Docs: docs/PR_FAQ.md, docs/RFC.md, docs/SCORECARD.md · Spikes: spike/ (quarantine) · Gates: K1–K5 + M0 battery bar.
- **STOPPED per Crucible: building belongs to $start-work after explicit approval.**

## Addendum 2026-09-11 — M0 echo-attribution KILLED (ADR-0011)
Rule works (+0.034 precision on 14/20 faults, zero recall cost, non-vacuous) but principled ceiling ≈0.76 < 0.85 bar. Residual is detector sensitivity (3/20 faults at R=0: F-06/F-12/F-14), not attribution. Side gain kept: AC@1-lat3 0.65→0.80. M0 re-scoped as build item **M0b detector-sensitivity** (missed-fault analysis first, no new infra, no more attribution work). Ship posture: CONDITIONAL at F1 ~0.73 with disclosed precision + recall/rank viva framing (PR/FAQ failure-reason #1 path).

## Addendum 2026-09-11 — Close-out (ADR-0012): zero known holes
DELAY (F1 0.670, AC@1 5/6, flip 24.2%) + LOSS (F1 0.739, AC@1 5/6, flip 30.3%) survive K1 per-class; 32-fault totals F1 0.725 AC@1 0.8125. RCAEval blind-spot does NOT reproduce. Class mitigations (tau≥d window, better imputation) ride as M1/M5 regression gates. FactorySimPy 0.1.0b3 API-unfit → KEEP-HANDROLLED (pinned). Pre-build triage COMPLETE.
