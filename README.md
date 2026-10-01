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
- `docs/MCP_EXPORT.md` — dry-run export envelopes. `docs/CI.md` — pipeline gates. `docs/FRONTEND.md` — /sim twin viewer (topology, panels, controls, feed, charts, gates). `docs/LINEAR_PLAYBOOK.md` — collaboration habits.
- `docs/PR_FAQ.md`, `docs/RFC.md`, `docs/ARCHITECTURE.md`, `docs/SPEC.md`, `docs/TECHNICAL.md`, `docs/PROBLEM.md`, `docs/RESEARCH.md`, `docs/SPIKES.md`, `docs/CONTRADICTIONS.md`, `docs/DIAGRAMS.md`, `docs/SCORECARD.md`, `docs/BUILD_BACKLOG.md` — Crucible dossier (frozen evidence).
- `.opencode/blackboard/anomaly-twin-trace/` — Crucible memory (ADR ledger, evidence, contradictions map).
- `spike/` — QUARANTINE (never merge, never import from `src/`; CI enforces): 5 harnesses + reports + JSONL traces.
- `.github/workflows/ci.yml` — brutal gates (lint-type/battery/killbars-security/e2e-demo/adversarial/docs-links/notify).
- `src/` — build root (created in M0; modules per SDD §2.2). `scripts/check_gates.py` + `scripts/linear_update.sh` + `demo/run.sh` — created with first build issues.

## Topology-A Twin Baseline & Schema v3 (M0.2e)

- **Schema & Version Pin**: `TWIN_SCHEMA = 3`, `CODE_VERSION = 'twin-2.2.0-topology-A'`. Atomic flag-day migration from v2.
- **Stratification Keys (M0.2e Contract)**: 9 exported stratification fields in `rec["strat"]` and Parquet columns:
  1. `wear_endpoint`: End-of-episode max machine wear scalar via minimal C3 wear-lite equation on active run/degraded steps without adding RNG streams.
  2. `maint_flag`: Boolean maintenance intervention indicator (honest deferral with unvalidated marker).
  3. `family`: Fault family classification (`clean`, `drift`, `delay`, `loss`, `spike`, `breakdown`, `quality`).
  4. `mode`: Operational degradation mode (`normal`, `observation_only`, `physical_propagation`).
  5. `root_id`: Primary injection root machine identifier resolved from event graph (depth <= 3).
  6. `root_ids`: Canonical collection of distinct root origins for multi-fault injections.
  7. `hop`: Shortest causal graph distance from root to detection (0 at root, -1 if clean).
  8. `sensor_vs_process`: Honest deferral to `'unknown'` with `sensor_vs_process_unvalidated=True`.
  9. `state_histogram`: Per-machine operational state time proportions obeying the strict denominator rule.
  - Auxiliary stratification context: `warmup_flag` (masks first 15 steps) and `funnel_census` (production throughput metrics).
- **Kit Funnel Rebalancing**: Rebalanced downstream kit assembly from starve state (13% yield, 22 median kits) to >= 30 median sunk kits via gated buffer unfreezing and AGV-priority variants. Rolling 20-seed evaluation achieves median sunk of **36.5** (p10=28.0, p90=39.0) with zero duty-cycle pile-up violations.
- **Zero-Join Dataset Export Contract (`src/dataset_export.py`)**:
  - Deterministic Parquet export with sorted column keys and bit-identical reproducibility.
  - Generates `window_config.json` (`schema_version=3`, `cal_win=120`, `T=300`, `warmup_steps=15`, owned field declarations).
  - Generates `metadata.json` / `ingestion_metadata.json` with dataset SHA-256 hash and funnel census summaries.
  - **Zero `scaler.pkl` Law**: Export-time scaling is strictly forbidden by TF1 leakage law to eliminate cross-fold data snooping.
  - Legacy v2 reader (`load_v2_dataset`) loudly raises `ValueError` on v3 records/datasets.
- **Hermetic Funnel Gate & Wall Report v2**:
  - Environment-pinned evaluation (`PYTHONHASHSEED=7`, `OMP_NUM_THREADS=1`).
  - `wall_report.json` schema v2 embeds funnel metrics (`median_sunk >= 30`).
  - Full-marker CI suite (`k1 or k2 or k3 or battery`) passes in ~14s (wall total < 600s budget).
  - Bit-identical jobs invariance across `--jobs 1` and `--jobs 4` (`d910d61123dfa80b87ef225b5be36e7a165d950be3ad1cc869370f36453976f5`).

## Verify (CPU-only; after M0 lands)
- Battery: `python scripts/run_battery.py` (gates via `scripts/check_gates.py`)
- Replay determinism: same `--seed 7` twice -> byte-identical (CI asserts)
- Docs: stale-token grep + lychee (CI asserts)
