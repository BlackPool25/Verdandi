# Test Plan ATT-TP-001 v1.0 / 2026-09-11 (IEEE 829)

## 1. Test Plan Identifier
ATT-TP-001 v1.0 / 2026-09-11
## 2. References
SRS.md (REQ-001–010), SDD.md, ELENCHUS_DISCOVERY.md V1-§§1–5, BUILD_BACKLOG.md M0b–M5, SPIKES.md.
## 3. Introduction
Prove viva-defensible trace over the entire factory flow: ranked cause + why-explanation per alarm. CONDITIONAL GO (line-scale baselines: AC@1 0.80–0.8125, flip 14.4–30.3%, 17.7s, grounding 1.00, 0-diverge 5×5; F1 gap → M0b).
## 4. Test items
twin.py (32-machine plant Lines A/B/C 10/10/8 + ASM0–2 + RWK0 + AGV/SBUF), detect.py, veto.py, walk.py, pcmci_job.py, narrate.py+verify.py, chaincards.py, replay.py, ui/, trail.py.
## 5. Software risk issues
RSK-001–008 (see REGISTERS.md); top: K1 causal instability, K2 threshold collapse, K3 hallucination.
## 6. Features to be tested
| REQ | TST | Gate |
|---|---|---|
| REQ-001/010 | TST-001 battery-F1-full-flow | fault-injection battery covering partitions × channels × classes (7 channels × 7 classes per SIM_SPEC §§5/8); PASS F1≥0.85 raw |
| REQ-001 | TST-002 causal-acc | masked PCMCI 5 seeds; PASS AC@1≥70% |
| REQ-010 | TST-003 flow-coverage | every machine × every fault class injected ≥1; whole-line replay context intact |
| REQ-002 | TST-005 grounding | sentence provenance audit; PASS ≥95% (obs. 1.00) |
| REQ-003 | TST-006 determinism | 5×5 same-seed replay; PASS 0-diverge |
| REQ-006 | TST-007 perf | CPU E2E; PASS <600s (line-scale baseline 17.7s) |
| REQ-006 flip | TST-003b stability | PASS flip<40% per partition per class (line-scale baseline 14.4–30.3%) |
| REQ latency | TST-004 latency | p99 detection delay ≤3 steps |
| REQ-007 | TST-008 shed-richness-first | 10x surge → shed rich sentences first, detection/provenance intact; PASS walk result served, no detection drop → TC-006b, TC-009 |
| REQ-008 | TST-009 per-run-caps | caps $0.005/2.5k tok/iter enforced; breach aborts rich first then hard-abort to chain-cards; PASS ledger audited → TC-007, TC-009 |
| REQ-009 | TST-010 no-clearance | twin/UI/trail never issue safety-restart clearance; PASS text audit 0 clearance strings → TC-011 |
## 7. features-NOT-tested
`derived-appendix: from V1-§5` — K1 causal unstable (AC@1<30%/flip>40%) → cut learning, keep topology+stats | reason: deferred-pivot. K2 threshold collapse (F1 drop>30pts) → per-machine quantile mandatory | reason: out-of-scope (global thresholds excluded). K3 ungrounded (>5%) → cut LLM to chain-cards | reason: deferred (free-LLM excluded). K4 diverge → subgraph-only replay | reason: out-of-scope (full-graph stochastic excluded). K5 ROCm sink (>1wk) → CPU-baseline | reason: deferred. Also excluded: blind discovery, Rust/Go core, pretrained reuse, live-streaming (killed, no trigger).
## 8. Approach
Fault-injection battery + 5-seed sweeps; frozen taus; report-only sensitivity; per-class DELAY/LOSS gates.
## 9. Item pass/fail criteria
- pass criterion: F1≥0.85 ∧ AC@1≥70% intra AND cross-partition ∧ flip<40% per partition per class ∧ p99≤3 steps ∧ <600s ∧ ≥95% ∧ 0-diverge ∧ full-plant coverage 32/32 machines (partitions × channels × classes, 7×7)
- fail criterion: any conjunct fails OR any sev-1 open → K-pivot fires
## 10. Suspension criteria and resumption requirements
- suspension criterion: seed-diverge OR ROCm blocker >1wk OR grounding <95% halts >50% cases
- resumption requirement: subgraph-only / CPU-baseline / chain-card fix + smoke TST-005/006/007 100% pass
## 11. Test deliverables
Battery CSV, sweep logs, verifier audit, replay diff, timing sheet, kill-bar verdict, flow-coverage matrix.
## 12. Remaining test tasks
M0b sensitivity (F-06/F-12/F-14) → battery re-run → closeout → viva dry-run.
## 13. Environmental needs
One CPU laptop, Python+SimPy stack, Gemini (Ollama fallback), topology local-only, seeded RNG.
## 14. Staffing and training needs
2–4 BTech, AI-assisted; no safety-clearance authority.
## 15. Responsibilities
Team runs battery; lead owns gates; professor viva dry-run arbiter.
## 16. Schedule
Wk1 battery+RQ2, Wk2 RQ3+RQ4, Wk3 RQ5+closeout+M0b.
## 17. Planning risks and contingencies
Hallucination→verifier; fragility→quantile; ROCm→CPU; drift→veto-mask re-spike.
## 18. Approvals
Sponsor (professor) / PM (team lead) / 2026-09-11.
## Glossary
AC@1 top-1 accuracy; flip edge-flip rate; 0-diverge byte-identical replay; chain-cards templated fallback.
