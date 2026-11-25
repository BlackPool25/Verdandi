# FINAL-e2e66check — PRISSUE-66 read-only verification (2026-11-25)

Worktree: `m0b-t-build` (Verdandi). Scope: read-only (no edits/commits/tests/Linear).

## (a) docs cite measured E2E 0.020 — CLEAN
- `docs/PROJECT_REPORT.md:142`: pooled coverage **0.020** (8/400), selective accuracy 0.625; splits s0 0.015@0.333 (3/200), s1 0.025@0.800 (5/200); abstain mix 233/72/87. Lineage `scripts/eval_e2e_selective.py`, seeds 0+1, n=400, live gate tau=0.739.
- `docs/SHIP_STATUS.md:31`: pooled coverage **0.020** (8/400), selective accuracy 0.625; per-seed 0.015@0.333 / 0.025@0.800; mix 233/72/87; lineage `artifacts/e2e-selective-n200-s{0,1}.json`.
- `docs/SHIP_STATUS.md:62`: PRISSUE-66 CLOSED — "E2E re-measured 0.020, derived 0.214 struck".

Surviving `0.214` in docs/ (3 hits, all struck-context — no stale live claim):
- `docs/PROJECT_REPORT.md:143`: "Abstain-gated (DERIVED — STRUCK 2026-11-25...): predicted ~0.214... Struck... do not cite. Superseded." — CLEAN (explicit strike).
- `docs/SHIP_STATUS.md:31`: "...which is why the DERIVED 0.214 below is struck, not adjusted." — CLEAN (explicit strike; refers to struck derived row in PROJECT_REPORT:143 + row 62).
- `docs/SHIP_STATUS.md:62`: "derived 0.214 struck — scope unchanged" — CLEAN (closure note).

No unstuck/unsigned 0.214 as current E2E. No other docs/ hits.

## (b) artifacts exist + measured lineage — CLEAN
- `artifacts/e2e-selective-n200-s0.json` EXISTS. `summary` (lines 2222-2235): n=200, coverage 0.015, n_covered=3, selective_accuracy 0.3333, risk 0.6667; abstain single-node 112 / silent-clean 39 / low-confidence-calibrated 46. `lineage` (2004-2220): battery `artifacts/m0b_mass_*.parquet (frozen, read-only)`, calibrator T=2.58/a=6.42017/b=-2.72362/tau=0.739/risk_target=0.3, gate `live src.diagnose.diagnose_incident + load_calibrator()`, trigger `oracle first fault_mask tick (perfect-retrieval assumption)`, scores `measured max|prefix-z| post-trigger window (not invented)`, seed 0.
- `artifacts/e2e-selective-n200-s1.json` EXISTS. `summary` (2222-2235): n=200, coverage 0.025, n_covered=5, selective_accuracy 0.8, risk 0.2; abstain 121/33/41. `lineage` identical except seed 1. Both carry `retrieval_lineage` + `pooled_coverage_composed` (s0 0.012, s1 0.02).
- Cross-check: 112+121=233 single-node, 39+33=72 silent-clean, 46+41=87 low-conf; 3+5=8/400=0.020 pooled; 1/3=0.333, 4/5=0.800, 5/8=0.625 — matches docs rows exactly.

## (c) lane report W-e2e66 claims match files — CLEAN
- `.superpowers/sdd/dx-followups/W-e2e66.md:37-41` table (s0 0.015 1/3 112/39/46; s1 0.025 4/5 121/33/41; pooled 0.020 5/8 233/72/87) == artifact summaries + docs rows above. Exact.
- W-e2e66:47-49 predecessor DERIVED 0.214 @ ~0.70 == struck rows PROJECT_REPORT:143 / SHIP_STATUS:31,62.
- W-e2e66:77-82 lineage (frozen battery, calibration.json T=2.58/a=6.4202/b=-2.7236/tau=0.739, live diagnose_incident + report.py single-node rule) == artifact `lineage` blocks.
- W-e2e66:3,83-84 "no commit (tree has other lanes' dirty files); merge stays with controller" — consistent: controller subsequently committed docs (see (d)); lane's "Proposed record insertions NOT applied" (68-75) were applied downstream, not by lane. No contradiction.

## (d) commit 6833590 present in log — CLEAN
- `git log --oneline --all`: `6833590 docs: E2E measured 0.020 replaces derived 0.214 (66 scope unchanged)` present (2026-11-25, full SHA 68335905dff995e9248418a67962c496bc7abe59). Related: `6f7034a data: measured selective E2E (n=400, coverage 0.020; derived 0.214 struck)`.

## Verdicts
- (a) docs 0.020 / 0.214 struck: CLEAN
- (b) artifacts lineage: CLEAN
- (c) W-e2e66 match: CLEAN
- (d) commit 6833590: CLEAN

Overall: ALL CLEAN — PRISSUE-66 disposition verified, no stale live 0.214, no mismatch.
