# Carry-Through — ADR verbatim + RFC + PR/FAQ

## 1. ADR verbatim block (IDs preserved, bytes from DECISIONS.md)
Status machine: proposed → accepted → superseded by ADR-###. Supersede-never-edit.

# ADR-0001: Project naming + memory root
Status: accepted. Context: Elenchus slug colocated. Options: anomaly-twin-trace vs factory-twin-rca vs viva-twin. Outcome: `anomaly-twin-trace`. Consequences: root ~/projects/anomaly-twin-trace/; memory .opencode/blackboard/anomaly-twin-trace/; spike/ quarantine.
# ADR-0002: Risk tier = Standard
Status: accepted. Standard rigor — 2 sweeps + 2 inversions + contradictions map + hardened spikes.
# ADR-0003 (T2): Constrained PCMCI, tau-small, depth≤3 — ACCEPTED
Decision: constrained PCMCI + depth≤3 + flip<40% gate (K1). Flip>40% → cut learning.
# ADR-0004 (T3): Template+verifier narration, chain-cards fallback, per-run caps — ACCEPTED
Decision: template+verifier primary; triple ≡ (fault-window, edge-id, detector-output); chain-cards fallback; caps mandatory. >5% ungrounded → chain-cards (K3).
# ADR-0005 (T4): CPU-baseline default, GPU-only-GNN inside 1-wk box — ACCEPTED
Decision: CPU-default; GPU only on clean driver spike in K5 box.
# ADR-0006 (T1): Fixed veto-mask + stats default; MP-discord challenger — ACCEPTED (challenger REJECTED in ADR-0009)
# ADR-0007: RQ3 template+verifier SPIKE-FEASIBLE — grounded 1.00@50coro, 5/5 hostile rejected, 0 egress.
# ADR-0008: RQ4/RQ5 SPIKE-FEASIBLE — 0-diverge 5×5, Kingman-80%.
# ADR-0009: RQ1/RQ2 battery CONDITIONAL GO — F1 0.734, AC@1 0.80, flip 14.4%, MP F1 0.063 REJECTED, quantile mandatory.
# ADR-0010: Phase-4 filing — PR/FAQ + RFC + scorecard + PLAN filed; Desirability L4 / Viability L3 / Feasibility L3.
# ADR-0011: M0 echo-attribution KILLED — dP +0.034, ceiling ≈0.76 < 0.85; M0b detector-sensitivity next.
# ADR-0012: Close-out — DELAY/LOSS survive K1; FactorySimPy 0.1.0b3 API-unfit → KEEP-HANDROLLED. Zero known pre-build holes.

## 2. RFC carry
Summary: Guardrailed twin-trace over the entire factory flow — hand-rolled SimPy 32-machine plant (Lines A/B/C 10/10/8 + ASM0–2 + RWK0, gateway buffers + AGV/SBUF, mass-flow-conserved coupling, partitioned causal evidence) with full material flow; quantile/IQR+veto detect; PCMCI tau-2 evidence-only; depth≤3 walk; template+verifier; seeded subgraph replay; CPU demo <10min. Alternatives: (1) Learned-GDN — GSL ineffective, no torch — rejected. (2) MP-discord — F1 0.063, 1700× slower — rejected as detector. (3) Free-LLM — 38.5% ungrounded + $47K-loop — rejected. Risks/Open: M0b F1 lift; wiring-time grounding %; tau-2 hold per class. Rollout: quantile → tau-2 → narration → replay → UI/trail; K1–K5 gates.

## 3. PR (≤1 page)
Heading: Every factory-twin alarm ships with its cause. Sub: ranked upstream cause (≤3 steps) + replay-backed why-explanation on one CPU laptop, modeled on the entire line. Summary 2026-09-11: 20-fault AC@1 80%, 17.7s, p99 3.7ms, grounding 1.00 template. Problem: 30–60min hand-triage; unverifiable viva stories. Solution: full-flow twin→detect→veto→walk→verify→replay→trail with triple provenance + 0-diverge replay + K1–K5 bars. Quotes: lead "no sentence without a triple"; examiner "show me the replay hash". CTA: run battery, pick any alarm, spot-check 3 triples, replay ×2.

## 4. FAQ
External: precision <0.85? → M0b on F-06/F-12/F-14, else ship disclosed. Hallucination? → verifier 1.00, 5/5 rejected, K3 fallback. Deterministic incl. full flow? → 0-diverge 5×5, else subgraph-only. Internal: PCMCI destabilizes? → flip gate per class; breach cuts learning (K1 parked). Fleet scale? → killed (Predix); single-twin semester scope.
