# EVIDENCE.md — L1 Curated Ledger (Tier-tagged, 2-domain rule)

## Corroborated (≥2-domain Tier 1–3 or contract + inversion-survived)
- FIXED topology prior > learned graph (RQ1). Informative topology helps on structured systems AND GDN-GSL learned-graph ineffective, GAT carries load [Tier1 Springer, defense + prosecutor concur]. T1 challenger sweep confirms: no deep model dethrones fixed-mask for short-run seeded CPU twin. Decision: fixed veto-mask default, never learned-graph.
- Guardrailed LLM-RCA pattern viable (RQ3-pattern). TAMO-FoA 76.3% −34%MTTR https://doi.org/10.1109/ccwc67433.2026.11393712 [Tier1] + KRCA AC@1 0.88/0.79 −77.3% https://arxiv.org/html/2607.01788 [Tier2→1] = 2-domain.
- RQ3 template+verifier SPIKE-FEASIBLE (harness-level). 50-coro grounded 1.00 (≥0.95); RSS 0.0%; 30/30 fallback ≤8s; 5/5 hostile rejected, 0 ungrounded, 0 egress; 10× keeps provenance (shed@500); mutation non-vacuous; caps $0.005/2.5k-tok. Code spike/rq3_spike.py, report spike/REPORT_RQ3.md. Caveat: mock narrator — full-LLM grounding measured when Gemini/Ollama wiring lands. K3 SURVIVES at template level.
- RQ4/RQ5 replay+timing SPIKE-FEASIBLE (harness lower-bound). Diverge 0 (5 seeds×5, PCG64/SeedSequence); 20-fault 0.001s total (<600s), p99 0.0001s; RSS +0.0%@10k; 50-coro ok; 10/10 malformed rejected; 10× flat, shed richness>6×; mutation non-vacuous; fan-out-8@depth3; Kingman-80% knee adopted. Code spike/spike_rq4_rq5.py, report spike/REPORT.md. Caveat: numpy-surrogate lower bounds — real path re-timed in battery (17.7s). K4/K5 SURVIVE.
- Battery real-path (RQ1/RQ2). quantile/IQR+veto F1 0.734 AC@1 0.80 p99 3.7ms wall 17.7s; PCMCI tau2 flip 14.4% lag-stab 0.889 n-stable 800; V1–V6 PASS. Report spike/REPORT_BATTERY.md.
- Close-out (DELAY/LOSS + FactorySimPy). DELAY F1 0.670 AC@1 5/6 flip 24.2%; LOSS F1 0.739 AC@1 5/6 flip 30.3%; 32-fault totals F1 0.725 AC@1 0.8125 p99 2.6ms; K1 survives per-class ×3 — blind-spot does NOT reproduce. FactorySimPy 0.1.0b3 installs but KEEP-HANDROLLED (no trace/fault/RNG API). Report spike/REPORT_CLOSEOUT.md.
- Echo rule micro-verified but INSUFFICIENT (M0). dP +0.034 on 14/20, dR 0, non-vacuous; principled ceiling ≈0.76 < 0.85 (spike/REPORT_M0.md). Side gain: AC@1-lat3 0.65→0.80.
- Fixed thresholds collapse (RQ5/K2). TCN-GAT SWaT 0.886→0.281 https://doi.org/10.1109/icci68752.2026.11506458 [Tier1] + SC-GAT raw 0.28 vs point-adjusted 0.92 [Tier1, 2-domain]. Consequence: per-machine quantile MANDATORY, fixed thresholds KILLED.
- Point-adjusted SOTA scores INADMISSIBLE vs raw F1≥0.85 bar (TimesNet 93→0.288, AT 94.07-point-adj/4.86M params [Tier2]). C3 ceiling judged on raw protocol only.
- PCMCI contract (RQ2-contract). run_pcmci(tau_max, pc_alpha, alpha_level) + CI suite https://github.com/jakobrunge/tigramite [Tier1, /jakobrunge/tigramite]; Bagged-PCMCI+ P/R gain [Tier2].
- Merlion DefaultDetector + RCAEval harness contracts (RQ4-contract). Merlion https://github.com/salesforce/merlion [Tier1, /salesforce/merlion]; RCAEval 735 cases/15 baselines https://doi.org/10.1145/3701716.3715290 [Tier1, /phamquiluan/rcaeval]. BUT Merlion ARCHIVED Mar-11-2026 [Tier2] → glue-only.
- Hand-rolled SimPy twin (no local clones; fresh pip; FactorySimPy rejected). UI waterfall via EvidencePanel.tsx:246 + GraphView.tsx (copy pattern, no Jaeger backend).

## Falsified / Killed (negative invariants)
- Learned-graph (GSL) as prior — ineffective [Tier1]. NEVER ship learned-graph.
- Fixed global thresholds — 53× shift collapse [Tier1×2]. NEVER fixed thresholds.
- ROCm-on-7900GRE as default — gfx1100 invalid-device + SVM/VRAM + VM-faults [Tier2×3]. DEFAULT = CPU-baseline; GPU-only-GNN iff boxed (K5).
- MP-discord as detector — battery F1 0.063, AC@1 0.20, 1700× slower (spike, real path). REJECTED; offline-validation pattern only.
- Echo-attribution as F1 closer — works (+0.034 P, 0 recall cost) but ceiling ≈0.76 vs 0.85 bar (spike/REPORT_M0.md). KILLED; no more attribution infra.
- FactorySimPy package — installs but API-unfit (spike). KEEP-HANDROLLED, pinned.
- MTAD-GAT / OmniAnomaly / Anomaly-Transformer / TimesNet for the twin — point-adjusted-only SOTA, raw-protocol collapse, heavy/stale stacks [Tier1/2]. NEVER as detector without raw-protocol proof.
- Blind discovery, Rust/Go core, pretrained weights, live-stream — killed [Tier2/3].
- Uptake-$160 endpoint — NOT reproduced, GAPPED. Never cited as proof.

## Contested → ALL RESOLVED (C1 harness-proven, C2/C3 battery-conditional, C4/C5/C6 proven)
- C1 95% bar: template-level PROVEN (1.00 harness); full-LLM grounding → M2 wiring-time measurement, chain-cards armed.
- C2/C3: AC@1 0.80–0.8125 (20–32 faults), flip 14.4–30.3% across 5 classes; F1 ~0.73 < 0.85, residual = sensitivity (F-06/F-12/F-14) → M0b build item.
- C4/C5/C6: 0 diverge, flat-10×, fan-out-5, 17.7s real-path; hand-rolled twin pinned.

## Gaps (budget-spent, explicit — all build-gated, none researchable pre-build)
- Full-LLM grounding % → M2 wiring. Sensitivity on missed faults → M0b. NOTHING else open.
