# Feasibility Scorecard — anomaly-twin-trace (CONDITIONAL GO)

Levels per technical-feasibility-matrix §4: L1 fatal/kill · L2 high/spike-required · L3 medium/ADR-tradeoff · L4 low/standard-practice.

| Dimension | Level | Rationale |
|---|---|---|
| Desirability | L4 | Ulwick cause-ranking 19, viva-trail 17 (ship≥10 ✓✓); POV/HMWs probed. |
| Viability | L3 | Semester scope, CPU-only 17.7s, capped COGS; ONE open bar (F1 0.734<0.85) with cheapest fix scoped (M0 echo-attribution, no infra). |
| Feasibility | L3 | All spikes + real-path battery pass kill bars; strict bar 2/3 → conditional, no pivot (K1 survives). |

## 15 stress questions (§5)
1. WAF peak random mutations? N/A (no storage engine; batch sim in-RAM).
2. Working-set > RAM read amplification? N/A (T=300–1200 windows, MiB-scale; RSS +0.0%@10k).
3. Consensus vs split-brain? N/A (no distributed writes; fencing N/A).
4. Fencing tokens on locks? N/A (no distributed locks).
5. Kingman wait at 85%? Shed-richness-first policy ≥80% adopted; 10× flat measured.
6. Fan-out cumulative p99? 50-coro p99 0.0001s–3.7ms; per-fault ≤30s with 1000× headroom.
7. KV-cache VRAM at peak? N/A (CPU path; template narration capped 2.5k tok/run).
8. Zero-JSON-failure automaton? Template schema + verifier gate (5/5 hostile rejected); full-LLM measured at wiring.
9. Dual-LLM quarantine for untrusted content? Local-first topology; 0 egress measured; no web/PDF ingestion in scope.
10. Roofline compute vs memory bound? N/A (stats path; PCMCI 0.21s/run CPU).
11. Condition number vs float precision? N/A (ParCorr on n≥800; min-n measured, not assumed).
12. 15s third-party tail? ≤8s deadline → chain-cards; 30/30 served 0.39s.
13. AZ-A drop bulkhead? N/A single laptop; Tier-1 paths (detection/provenance) never shed.
14. Pre-mortem scenario? F1 drift-silence → versioned quantile + K2 alarm; F2 theater → triple+mutation gate; F3 diverge → SeedSequence+subgraph-only.
15. **Why-Now 10× shift?** Semester inversion (Elenchus-tested): sim ownership zeroes upkeep + free ground truth/replay — Predix economics NOT transferred; guardrailed LLM-RCA 10× $/incident (TAMO-FoA/KRCA 2-domain) transfers. NO 10× claimed for prod upkeep or raw GNN scale (both killed).
