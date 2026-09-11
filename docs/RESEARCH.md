# RESEARCH — anomaly-twin-trace (asymmetric pairs, Tier-tagged, 2-domain rule)

Method: librarian-defense (Context7 ≤3/query + academic) vs prosecutor (inversion matrix
`<tech> (outage OR "write stall" OR "memory leak" OR deadlock OR CVE OR postmortem)`); oracle ATAM;
6-vector spikes. Tier 5 banned as proof. Full logs purged per protocol; verdicts below.

## RQs → outcomes
- **RQ1 detector:** fixed veto-mask+stats STANDS (GSL ineffective [Tier1 Springer]); challengers dead —
  MP-discord F1 0.063/AC@1 0.20/1700× slower (spike); USAD 2026 P/R ~0.79–0.80 < bar;
  MTAD-GAT/OmniAnomaly/AT/TimesNet point-adjusted-only + raw collapse (TimesNet 93→0.288) [Tier1/2].
- **RQ2 PCMCI stability:** contract (/jakobrunge/tigramite) [Tier1]; 5-seed flip tau2 14.4% / tau3 21.2%,
  lag-stab 0.889, n-stable 800 (spikes). Spurious-risk literature survives → tau=2 + flip gate (K1).
- **RQ3 grounding:** pattern 2-domain (TAMO-FoA 76.3% −34%MTTR https://doi.org/10.1109/ccwc67433.2026.11393712
  [Tier1] + KRCA 0.88/0.79 −77.3% https://arxiv.org/html/2607.01788 [Tier2→1]); template spike 1.00@50coro;
  vs OpenRCA2.0 38.5% ungrounded https://doi.org/10.48550/arxiv.2606.27154 [Tier1] → verifier+fallback mandatory.
- **RQ4 replay:** 0-diverge 5×5 (SeedSequence) harness + battery; FactorySimPy discrete-only/static [Tier2] →
  hand-rolled twin pinned.
- **RQ5 perf:** CPU 17.7s/32-faults, p99 ≤3.8ms; ROCm default KILLED (gfx1100 #12045 + SVM #5952 + VM-faults #6529 [Tier2]).
- **Collapse proof:** TCN-GAT SWaT 0.886→0.281 https://doi.org/10.1109/icci68752.2026.11506458 [Tier1] +
  SC-GAT raw 0.28 vs adjusted 0.92 → per-machine quantile mandatory.
- **Scale ceiling:** GNN OOM 500k–1M [Tier1]; RCAEval best Avg@5 0.46–0.54 [Tier1] (raw protocol only).
- **Caps:** $47K/264h loop [Tier2] → per-run token/USD/iter caps. Graveyard: Predix $4–7B / Uptake / TensorZero
  (archived Jun-2026) / EGADS / Twitter-AD → prod framing killed; semester inversion (free sim truth) transfers.
- **KQs closed:** stable-n 800 · fan-out-5 · Kingman-80% · 95%-bar template-proven · AC@1 ceiling +60pts over MP.

## Contradictions C1–C6 → resolutions (see CONTRADICTIONS.md)
C1 95% bar → template-proven, LLM open (M2) · C2 PCMCI → flip-gated tau-2 · C3 AC@1≥70% → 0.80–0.8125 real-path,
F1 conditional (M0b) · C4 replay → 0-diverge · C5 walk → capped+flat-10× · C6 sim → hand-rolled pinned.

## Kill table (all load-bearing assumptions met their killer criterion or survived it)
K1 SURVIVE (AC@1 0.80–0.8125 / flip ≤30.3%) · K2 FIRES→quantile (learning cut) · K3 SURVIVES (harness) ·
K4 SURVIVES · K5 SURVIVES (CPU) · echo-hypothesis KILLED (ceiling ≈0.76) · MP KILLED · ROCm KILLED ·
fixed-thresholds KILLED · learned-graph KILLED · blind/Rust/pretrained/live KILLED.
