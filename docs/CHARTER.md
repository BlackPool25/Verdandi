# Project Charter (PMBOK, ≤3 pages) — anomaly-twin-trace
## 1. Purpose
BTech team needs ranked causal trace + why-explanation for every factory-twin alarm; detectors alone cost 30–60 min hand-triage and unverifiable stories lose viva marks. Every flag ships its proof in <10 min on one laptop, grounded in the entire factory flow.
## 2. Measurable objectives + success criteria
F1≥0.85 | success: battery raw ≥0.85. AC@1≥70%@20f | success: ≥70%. Latency ≤3 steps. E2E <600s (17.7s line-scale baseline). Grounding ≥95% (obs. 1.00). Flip<40% per partition per class. 0-diverge 5×5. Full-plant coverage 32/32 machines, partitions × channels × classes (7 classes, 7 channels).
## 3. High-level scope (in / out)
In: full-plant SimPy twin (32 machines: Lines A/B/C 10/10/8 + ASM0–2 + RWK0, gateway buffers + AGV/SBUF, mass-flow-conserved coupling, partitioned causal evidence), detect, veto, walk, PCMCI-evidence, template+verifier narration, seeded replay, waterfall UI, viva trail. Out: safety-restart clearance (human-only), prod upkeep/scale, blind discovery, Rust/Go, pretrained reuse, live-streaming. Boundaries: semester demo only, not prod twin.
## 4. Milestones (single timeline Wk1–Wk14, aligned with TEST_PLAN gates)
| Milestone | Date |
|---|---|
| Wk1–Wk2 kickoff + twin skeleton (32-machine plant per SIM_SPEC §2) | Wk2 |
| M0b F1 closure | Wk4 |
| M1 hardening + class gates | Wk6 |
| M2 narration wiring | Wk8 |
| M3 replay + demo harness | Wk10 |
| M4 UI + trail | Wk12 |
| M5 viva dry-run | Wk14 |
## 5. Budget (preapproved)
CPU-only, zero GPU spend.
- Per-run caps: $0.005 / 2.5k tokens / iter cap.
- Per-incident: <$0.50 / <60s.
## 6. Key stakeholders
Team (user) → STK-001; Operators → STK-002; Professor (buyer) → STK-003; Lab infra → STK-004 (see REGISTERS.md).
## 7. High-level risks + assumptions/constraints
Top risks → RSK-001–008 (Predix/Uptake/EGADS lessons; threshold fragility; hallucination; ROCm sink). Assumptions: skeleton stable; short-run lags stable; grounding ≥95% (all ASSUMED pending spikes). Constraints: local-first, CPU-only, anonymized traces, no safety authority.
## 8. Authority
Project Manager: team lead — Authority: decides scope/schedule/budget within semester demo limits; escalates to professor (sponsor) beyond that.
## 9. Approval + Signatures
| Role | Name | Signature | Date |
|---|---|---|---|
| Sponsor | Professor | <Signature> | 2026-09-11 |
| Project Manager | Team lead | <Signature> | 2026-09-11 |
