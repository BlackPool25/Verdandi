# Verdandi — every factory alarm ships with its proof

Verdandi, Norn of *what-is*: a 32-machine factory twin where every alarm arrives with a ranked upstream cause (≤3 steps + gateway), a why-explanation (≥95% triple-grounded sentences), and a seeded replay proving it — on one CPU laptop, end-to-end demo under 10 minutes.

**Status: CONDITIONAL GO** (Crucible stress-tested, pre-build). K1/K3/K4/K5 survive · K2 mandates quantile · F1 ~0.73 < 0.85 bar (→ M0b sensitivity first) · zero known pre-build holes.

## Bars (ship thresholds — NEVER soften without L1 reclassification)
F1 ≥ 0.85 · AC@1 ≥ 70% intra+cross-partition · latency ≤ 3 steps · demo < 10 min ·
grounding ≥ 95% · flip < 40% per partition · 0-diverge. K1 AC@1<30%/flip>40%→cut learning ·
K2 F1-drop>30pts→quantile mandatory · K3 >5% ungrounded→chain-cards · K4 diverge→subgraph-only ·
K5 ROCm>1wk→CPU-baseline. Twin NEVER issues safety-restart clearance.

## Links
- GitHub: https://github.com/BlackPool25/Verdandi
- Linear: Verdandi project (team MCP, milestones M0–M5, issues MCP-10–18)
- Playbooks: docs/LINEAR_PLAYBOOK.md (team habits) · docs/CI.md (brutal gates)

## Map
- `ELENCHUS_DISCOVERY.md` — validated problem brief (V1 payload; slug anomaly-twin-trace frozen in Crucible sources).
- `PLAN.md` — verified goal, build order M0→M5, stack, reuse, acceptance, HANDOFF.
- `docs/SRS.md` — IEEE 29148 requirements (REQ-001–010).
- `docs/SDD.md` — IEEE 1016 design (8 viewpoints + module specs + data dictionary + mermaid).
- `docs/SIM_SPEC.md` — normative 32-machine plant spec (lines A/B/C + assembly + rework + AGV, true coupling, 7 fault classes, 7 channels).
- `docs/TEST_PLAN.md` — IEEE 829 plan (TST-001–010). `docs/TEST_CASES.md` — concrete cases TC-001–011.
- `docs/CHARTER.md` + `docs/REGISTERS.md` — PMBOK charter, stakeholders, risks.
- `docs/CARRY_THROUGH.md` — ADR-0001–0012 verbatim + RFC + PR/FAQ. `docs/SPRINT_PACK.md` + `docs/BACKLOG_DETAIL.md` — stories + task backlog.
- `docs/MCP_EXPORT.md` — dry-run export envelopes. `docs/CI.md` — pipeline gates. `docs/LINEAR_PLAYBOOK.md` — collaboration habits.
- `docs/PR_FAQ.md`, `docs/RFC.md`, `docs/ARCHITECTURE.md`, `docs/SPEC.md`, `docs/TECHNICAL.md`, `docs/PROBLEM.md`, `docs/RESEARCH.md`, `docs/SPIKES.md`, `docs/CONTRADICTIONS.md`, `docs/DIAGRAMS.md`, `docs/SCORECARD.md`, `docs/BUILD_BACKLOG.md` — Crucible dossier (frozen evidence).
- `.opencode/blackboard/anomaly-twin-trace/` — Crucible memory (ADR ledger, evidence, contradictions map).
- `spike/` — QUARANTINE (never merge, never import from `src/`; CI enforces): 5 harnesses + reports + JSONL traces.
- `.github/workflows/ci.yml` — brutal gates (lint-type/battery/killbars-security/e2e-demo/adversarial/docs-links/notify).
- `src/` — build root (created in M0; modules per SDD §2.2). `scripts/check_gates.py` + `scripts/linear_update.sh` + `demo/run.sh` — created with first build issues.

## Verify (CPU-only; after M0 lands)
- Battery: `python scripts/run_battery.py` (gates via `scripts/check_gates.py`)
- Replay determinism: same `--seed 7` twice → byte-identical (CI asserts)
- Docs: stale-token grep + lychee (CI asserts)
