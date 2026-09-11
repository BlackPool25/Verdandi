# Press Release: anomaly-twin-trace — every factory-twin alarm ships with its cause

A BTech team running a FactorySimPy twin used to hand-triage every alarm for 30–60 minutes and defend unverifiable stories in viva. With anomaly-twin-trace, every flag arrives with a ranked upstream cause (≤3 steps) and a replay-backed why-explanation in which ≥95% of sentences resolve to a (fault-window, edge-id, detector-output) provenance triple — on one CPU laptop, end-to-end demo under 10 minutes, 20-fault battery AC@1 80%.

## Customer FAQ
- **What do I get?** Ranked cause + chain-card explanation + seeded replay evidence per alarm.
- **How accurate?** Battery (real path, raw protocol): F1 0.734 (R 0.912 / P 0.614), AC@1 80%@20 faults, PCMCI flip 14.4% (5 seeds). F1 bar 0.85 is CONDITIONAL — precision gap (downstream echoes) closes in M0 echo-aware attribution; no new infra.
- **What hardware?** One CPU laptop. 17.7s full battery; p99 3.7ms/fault. No GPU (ROCm path killed by driver triple-hit evidence).
- **What if the LLM hallucinates blame?** Template+verifier blocks it: spike proves 1.00 grounding@50 coroutines, 5/5 hostile payloads rejected, 0 egress; >5% ungrounded auto-falls-back to chain-cards (K3).
- **Deterministic?** 0 divergences over 5 seeds×5 replays (SeedSequence discipline); diverge would force subgraph-only mode (K4, never triggered).

## Internal Skeptical Engineering FAQ
- **Scale dynamics:** Single-twin semester scope; walk capped depth≤3 (fan-out-5 measured); 10×-ingress flat, richness shed first, provenance never shed. NOT a prod fleet story — prod framing explicitly killed (Predix logic).
- **Blast radius:** Twin never issues safety clearance (human-only restart). Worst failure = wrong rank in a demo + viva probe exposure; mitigated by triple-resolution + mutation-gated verifier.
- **Degraded dependencies:** Gemini/Ollama 15s tail → ≤8s deadline → local chain-cards (spike: 30/30 served in 0.39s). Merlion archived → glue-only. No distributed locks (batch sim, fencing N/A).
- **COGS:** CPU-only, per-run token/USD/iteration caps (答 $47K-loop precedent); full battery 17.7s wall.
- **Consensus SPOF:** None — no consensus, no shared mutable state across processes.

## Provenance-first wedge (conditional on H4 audit)
Moat is the provenance leg Eadro/RCAEval lack: every sentence resolves to a (fault-window, edge-id, detector-output) triple or serves explicit fallback.
Wedge is the conjunction T+P+R (template + provenance triple + seeded replay), not any single leg.
If H4 fails, packaging/pedagogy fallback is pre-agreed: ship chain-cards + trail as the product, no verifier-superiority claim.
Brownfield transfer disclosure: topology drift, sensor noise, and operator trust are unmeasured and out-of-semester; the wedge holds for the sim twin only.

## Top 3 reasons this will not succeed (+ proving evidence)
1. **Precision never reaches 0.85** (echo FPs resist attribution) → prove by M0 battery re-run F1≥0.85; else ship at 0.734 with disclosed precision + viva framing on recall/rank.
2. **Full-LLM grounding collapses at wiring time** (template 1.00 ≠ LLM fluency) → prove by wiring-time grounding measurement; K3 fallback (chain-cards) already armed and spiked.
3. **PCMCI destabilizes on richer faults** (tau-3 flip 21.2% hints the edge) → prove by battery flip<40% gate per new fault class; breach cuts learning to topology+stats (K1 pivot, parked).
