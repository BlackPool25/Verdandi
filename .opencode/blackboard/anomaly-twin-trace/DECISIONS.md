# DECISIONS.md — L1 ADR Ledger

## ADR-0001: Project naming + memory root
- Context: user asked for good name in ~/projects + Elenchus/Crucible colocated.
- Options: anomaly-twin-trace (Elenchus slug) vs factory-twin-rca vs viva-twin.
- Decision: `anomaly-twin-trace` — preserves Elenchus slug, kebab-case <50ch, captures ranked-trace essence.
- Consequences: root `~/projects/anomaly-twin-trace/`; memory `.../.opencode/blackboard/anomaly-twin-trace/`; spike/ quarantine at project root.
- Reversibility: Type 2 (rename cheap). Status: accepted.

## ADR-0002: Risk tier = Standard
- Context: semester demo, reversible pivots (minimal-twin), new deps (GDN/PCMCI/LLM), no prod safety authority.
- Decision: Standard rigor — 2 sweeps + 2 inversions + contradictions map + hardened spikes for L2 assumptions.
- Reversibility: Type 2. Status: accepted.

## ADR-0003 (T2): Constrained PCMCI, tau-small, depth≤3 — ACCEPTED
- Context: oracle ATAM T2; user fork pick 2026-09-11. Rich lags catch long-delay faults but risk spurious edges (C2 [Tier1]) + exponential walk (C5 [Tier2]).
- Decision: constrained PCMCI + depth≤3 cap + edge-flip<40% gate (K1); richness only if S1 p99 headroom >30%.
- Consequences: RQ2 5-seed lag sweep decides; flip>40% → cut learning (topology+stats).
- Reversibility: Type 2. Status: accepted.

## ADR-0004 (T3): Template+verifier narration, chain-cards fallback, per-run caps — ACCEPTED
- Context: oracle ATAM T3; user fork pick. Free-LLM fails grounding (OpenRCA2.0 38.5% ungrounded [Tier1]) + $47K loop precedent [Tier2].
- Decision: template+verifier primary (provenance-id must resolve to fault-window/edge-id/detector-output triple — pre-mortem F2 seed); chain-cards hard fallback; token/USD/iteration caps mandatory.
- Consequences: RQ3 spike must prove ≥95% grounding + 100% malformed rejection + mutation gate; >5% sans valid triple → chain-cards (K3).
- Reversibility: Type 2. Status: accepted.

## ADR-0005 (T4): CPU-baseline default, GPU-only-GNN inside 1-wk box — ACCEPTED
- Context: oracle ATAM T4; user fork pick. ROCm triple-hit (gfx1100 #12045 + SVM #5952 + VM-faults #6529 [Tier2]).
- Decision: CPU-default; GPU revives only on clean driver spike inside K5 1-wk timebox.
- Consequences: RQ5 timing spike on CPU; demo never depends on GPU.
- Reversibility: Type 2. Status: accepted.

## ADR-0006 (T1): Fixed veto-mask + stats default; MP-discord spike-gated challenger — ACCEPTED
- Context: oracle ATAM T1 REC + user "research better approach" + librarian T1 sweep (Tier1, 2-domain: MMPAD-#1-TSB-AD + 19-baseline/119-dataset + STUMPY /stumpy-dev/stumpy). Deep models rejected (point-adjusted-only, raw collapse, heavy/stale).
- Decision: fixed-mask default STANDS; matrix-profile discord sole sanctioned challenger — promote iff F1≥0.85 + flip<20% + faster/simpler on 20-fault battery; USAD second-line only.
- Consequences: battery pits quantile/IQR vs discord; point-adjusted scores inadmissible.
- Reversibility: Type 2. Status: accepted (challenger subsequently REJECTED in ADR-0009).

## ADR-0007: RQ3 template+verifier SPIKE-FEASIBLE (harness-level)
- Spike spike/rq3_spike.py: grounded 1.00@50coro, RSS 0.0%, 30/30 fallback ≤8s, 5/5 hostile rejected, 10× provenance-kept, mutation non-vacuous, caps enforced. K3 SURVIVES at template level; full-LLM grounding measured at wiring time. Report spike/REPORT_RQ3.md. Status: accepted.

## ADR-0008: RQ4/RQ5 replay+timing SPIKE-FEASIBLE (harness lower-bound)
- Spike spike/spike_rq4_rq5.py: diverge 0 (5×5 SeedSequence), 20-fault 0.001s, p99 0.0001s, RSS +0.0%@10k, 10× flat shed-richness>6×, mutation non-vacuous, fan-out-8, Kingman-80%. K4/K5 SURVIVE at harness level; figures are LOWER BOUNDS (numpy surrogate) — real path re-timed in battery. Report spike/REPORT.md. Status: accepted.

## ADR-0009: RQ1/RQ2 battery — CONDITIONAL GO (K1 survive / K2 fires / MP rejected)
- Battery spike/battery_rq1_rq2.py, real path (simpy 4.1.2, stumpy 1.14.1, tigramite 5.2.10.1), wall 17.7s: quantile/IQR+veto F1 0.734 (P 0.614/R 0.912) AC@1 0.80 AC@1-lat3 0.65 p99 3.7ms; MP-discord F1 0.063 AC@1 0.20 1700× slower → REJECTED (K2 fires: quantile mandatory, learning-detection CUT); PCMCI tau2 flip 14.4% tau3 21.2% lag-stab 0.889 n-stable 800; GDN skipped (no torch); V1–V6 PASS (V3 20ms scaled probe of 200ms spec — accepted, mechanism identical).
- Decision: ship quantile/IQR + fixed veto-mask; PCMCI tau=2 evidence-only (never production edges); strict bar 2/3 → CONDITIONAL, no minimal-twin pivot (K1 survives); F1 gap = precision (downstream echoes) → M0 echo-aware attribution, no new infra.
- Reversibility: Type 2. Status: accepted.

## ADR-0010: Phase-4 filing (PR/FAQ + RFC + scorecard + PLAN)
- Gate rule satisfied: docs/PR_FAQ.md + docs/RFC.md + docs/SCORECARD.md (15 questions incl. Q15 Why-Now) + PLAN.md filed. Feasibility: Desirability L4 / Viability L3 / Feasibility L3 → CONDITIONAL GO. Awaiting user plan approval; no build without it. Status: accepted (plan pending approval).

## ADR-0011: M0 echo-attribution — KILLED (honest falsification, project stays CONDITIONAL)
- Spike spike/m0_echo.py, real 20-fault path, wall 8.4s: rule (upstream score≥downstream in [t−W−(m−u), t], W=5=tau2+LAT3) gives dP +0.034 on 14/20 faults, dR exactly 0, non-vacuous (inversion 0.726→0.699); principled-variant ceiling ≈0.76 (score-less windows lose recall → rejected). F1 0.726 misses 0.85 by 12.4pts. Residual is structural: 3/20 faults at R=0 (F-06/F-12/F-14 sensitivity, nothing to attribute) + M5 noisy-channel FPs + echo tails. Side gain: AC@1-lat3 0.65→0.80. OFF-baseline jitter 0.734→0.700 cross-run is hash()-seed noise (within-run delta valid).
- Decision: KILL echo-attribution as the F1 closer; next cheapest step is detector-sensitivity work on missed faults (M0b, build phase) — NOT more attribution, no new infra. No bar softened. Report spike/REPORT_M0.md. Status: accepted.

## ADR-0012: Close-out — DELAY/LOSS classes survive; FactorySimPy rejected (KEEP-HANDROLLED)
- Spike spike/closeout.py, wall 3.1s: DELAY F1 0.670 AC@1 5/6 flip 24.2%; LOSS F1 0.739 AC@1 5/6 flip 30.3%; base reproduces (0.739/0.80/14.4%); totals 32 faults F1 0.725 AC@1 0.8125 p99 2.6ms. K1 SURVIVES per-class ×3 and globally — RCAEval blind-spot does NOT reproduce. Class mitigations noted (tau≥d window, better imputation), no global pivot. Per-class MP re-run skipped (dead path, waste).
- FactorySimPy: factorysimpy==0.1.0b3 installs (PyPI, MIT), 3-machine line 0.01s — but discrete-only counts, no signal-trace API, no seeded-fault params, no RNG hooks → strictly MORE glue. Verdict KEEP-HANDROLLED (pinned). Report spike/REPORT_CLOSEOUT.md.
- Zero known pre-build holes remain. Status: accepted.
