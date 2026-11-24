# DX Full Plan — 15 Linear issues on m0b-t-build (2026-11-24)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement task-by-task. Steps use checkbox (`- [ ]`) syntax.
> Research briefs: `.superpowers/sdd/dx-proper/research-{calibration,tev,react}.md` + `SOLVE_GAPS.md` (per-issue gaps). Read the brief for your task first.

**Goal:** Close all 15 assigned Linear issues with measured evidence, integrated into the existing React `/sim` viewer. No new frontend, no theme/UX changes, no twin physics changes.

**Architecture:** `diagnose_incident (+calibrated conf) → emit_packet → jev-decide-or-template → build_card/build_dossier → report_incident.py artifacts → DiagnosisCard/DossierView panels in /sim`. Offline-first; LLM rephrases prose only, never decides.

**Tech Stack:** Python (existing src/), React 19 + Zustand (existing /sim), FastAPI sim_bridge (SSE untouched), LightGBM ranker, Ollama tev1:4b (eval/phrasing only), HF RoBERTa-MNLI (faithfulness NLI, CPU offline).

## Global Constraints

- CPU-only, wall <600s, p99 ≤3s, narration ≤8s fallback; 5× same-seed 0-diverge; TWIN_SCHEMA v6 + 10-key tick contract frozen; single EventSource SSE contract untouched; PA-OFF raw scoring; no safety-clearance authority.
- Kill bars: F1 ≥0.85, AC@1 ≥70%, flip <40%, grounding ≥95% (else template), forced top-1 shift ≤0.01 on calibration, Tev machine <0.3 → struck as decider, rerank <0.70 after ≤2 variants → struck, PPR <+0.03 over 0.162 → diagnostic-only, judge flip >20% → P/R only, any invented number → template only.
- Measured-only: every number recorded with n/seed/lineage or it didn't happen. Stubs/fixtures/same-grid tuning never cited as general evidence.
- T12 gates stay green (palette, scope grep, tsc, vitest incl. render-counter + a11y, bridge pytest/ruff/mypy). Additive UI only.

## Review Focus

- Abstain renders reason + coverage, never a guess — else silent ungrounded pass.
- Calibrated conf must not move top-1; heuristic `_eweight` scores must never feed temperature scaling.
- τ=0.080 (all-windows) gates nothing — serve held-5 τ=0.739 only.
- LLM numbers/IDs must equal packet verbatim (diff gate) — else grounding collapse.
- Same-grid tuning cited as same-grid only; held-out seeds owed before general claims.

---

### Task 1: Ship/scope/defer docs (66, 65, 70, 69)

**Files:** Modify `docs/PROJECT_REPORT.md`; Create `docs/SHIP_STATUS.md`.
**Interfaces:** Produces scope list + reason codes consumed by Tasks 7–10 (`ship | abstain_sensor | abstain_weak_family | abstain_transfer | abstain_low_conf | abstain_rerank | abstain_paths | abstain_tev`).

- [ ] Step 1: Sign 66 scope (ship = detect + process attribution + calibrated abstain; rest abstain with codes) + recompute pooled E2E under coverage/selective risk; sign 65-B sensor abstain (0.03–0.07 vs 0.4 bar + dual-obs Goodhart risk); sign 70 permanent deferral; write 69 SHIP_STATUS.md (status + struck ledger + open links).
- [ ] Step 2: Verify — `Select-String "abstain" docs/PROJECT_REPORT.md docs/SHIP_STATUS.md` shows scope table + all codes + signatures.
- [ ] Step 3: Commit `docs: signed ship scope + deferrals (66/65/69/70)`.

### Task 2: Open-set retrain + ranker calibration (75)

**Files:** Run `scripts/eval_stacked.py`; Create `artifacts/stage2-oof.npz` (force-add, gitignored dir) + calibrator JSON; Modify `docs/DIAGNOSIS_QUALITY.md` (record).
**Interfaces:** Produces stage2-oof.npz consumed by Task 6; ranker T/Platt consumed by Task 5.

- [ ] Step 1 (RED): Add/extend test asserting `eval_stacked.main` saves `artifacts/stage2-oof.npz` with expected keys; run → FAIL (missing).
- [ ] Step 2 (GREEN): Rerun `eval_stacked.main`, fit ranker-level T+Platt (ECE/NLL/risk-coverage + abstain-gated rerank numbers), exclude-held-5 retrain for true unknown-reject. Minimal code to pass.
- [ ] Step 3: Record ECE/NLL/risk-coverage + abstain-gated rerank + transfer numbers in DIAGNOSIS_QUALITY; run full suite green; commit `data: stage2-oof + ranker calibration (75)`.

### Task 3: v2 general battery (74)

**Files:** Run `scripts/gen_mass_battery.py`, `cache_windows.py`, `eval_fire_flow.py`; Modify `docs/SIM_BASELINE.md` (record).
**Interfaces:** Produces keep/scope verdict consumed by Task 1 scope (update if scoped).

- [ ] Step 1: Generate full 7-family × 2-rung seed-identical OFF/ON grids + both caches (same n_per_cell; document seeds).
- [ ] Step 2: Run `eval_fire_flow` obs-only + obs+flow @ thr 0.5/0.7 both arms; keep general claim iff ON beats OFF at matched clean-fire on FULL mix, else scope win to quality/loss explicitly in SIM_BASELINE. **Scope-amendment rule:** if the verdict changes the Task 1 scope (ship vs abstain on v2-gated families), amend SHIP_STATUS + PROJECT_REPORT §8 in this step and note it in the commit.
- [ ] Step 3: Verify gates on genuine numbers; commit `data: v2 full-mix verdict (74)`.

### Task 4: Tev at scale (62)

**Files:** Modify `scripts/eval_tev.py` (n=60 pinned seed); Modify `docs/DIAGNOSIS_QUALITY.md` (record). Needs local Ollama `tev1:4b`; if unavailable, record BLOCKED honestly, do not fake.
**Interfaces:** Produces win/kill verdict; kill → phrasing-only disposition (Task 9).

- [ ] Step 1: Extend eval to n=60 rich-criteria pinned seed; report machine top-1 vs teacher 0.671 + family + null.
- [ ] Step 2: If machine <0.3, run self-consistency n=5 machine-only re-measure once; strike as decider if still <0.3 (keep phrasing-only disposition, ranker stays decider).
- [ ] Step 3: Record numbers; commit `data: tev n=60 verdict (62)`.

### Task 5: Rerank variants + path teleport (63, 64)

**Files:** Modify `scripts/eval_stacked.py` (variant 1: calibrated rerank on stage2-oof; variant 2 if needed: per-family heads or pairwise/truncation config); Modify path scorer + `scripts/eval_paths.py` (teleport = ranker-softmax × flow mass, α=0.85); record in DIAGNOSIS_QUALITY.
**Interfaces:** Consumes stage2-oof.npz (Task 2). Produces keep/strike verdicts.

- [ ] Step 1 (RED): Failing test asserting calibrated-rerank path exists and votable computed on identical CV/episodes. Baseline is the Task 2 rerun (teacher 0.654, stage2-oof.npz committed): gap to bar is +0.033.
- [ ] Step 2 (GREEN): Variant 1 (post-hoc, minutes); variant 2 only if <0.70. Max 2 total. Strike if <0.70 (bar stays missed, abstain-gate ships without it). Identical episodes/CV/groups; report votable + pooled.
- [ ] Step 3: PPR teleport, re-run ranked arm same n=167 seed; keep iff root-hit@1 ≥0.192 with subseq@3 ≥0.413, else stays diagnostic-only.
- [ ] Step 4: All green; commit `feat: rerank + path verdicts (63/64)`.

### Task 6: Faithfulness harness (72)

**Files:** Modify `scripts/eval_jev.py` (add citation recall + local NLI entailment per claim); Modify `docs/DIAGNOSIS_QUALITY.md` (record template P/R + entailment). LLM-judge (3-run + position-swap) key-gated, non-blocking.
**Interfaces:** Consumes recorded packets; template baseline consumed by Task 9.

- [ ] Step 1 (RED): Failing test for recall computation on a recorded packet fixture.
- [ ] Step 2 (GREEN): Implement recall + entailment (HF roberta-large-mnli CPU offline); run; record. Judge gated with flip-rate disclosure.
- [ ] Step 3: Commit `feat: faithfulness recall + NLI (72)`.

### Task 7: Calibration gate wiring (61)

**Files:** Modify `src/diagnose.py` (`diagnose_incident` loads `artifacts/calibration.json {T:2.58,a,b,tau:0.739}`, gates after rank before `build_report`, persists conf+tau), incident store schema (+conf/tau columns); Create `artifacts/calibration.json`; test file for gate + kill bar.
**Interfaces:** Consumes Task 1 scope codes + Task 2 ranker numbers (log only). Produces calibrated packet conf consumed by Tasks 8–10.

- [ ] Step 1 (RED): Failing test — calibrated conf present on every non-abstain report; conf<τ → abstain card with reason `low-confidence-calibrated`; forced top-1 shift ≤0.01 vs uncalibrated.
- [ ] Step 1b (VERIFY gate, required): re-measure τ=0.739 on exclude-held data before serving. If risk>0.3: re-pick τ at budget and record, or re-scope with SHIP_STATUS + PROJECT_REPORT §8 amendment. Never serve ranker τ=0.187 on the report path (different margin definition).
- [ ] Step 2 (GREEN): Minimal wiring (gate-only, no re-rank; heuristic scores never into temperature). Held-5 check: abstain ≈0.66 @ risk ≈0.3.
- [ ] Step 3: Full suite green; commit `feat: calibration gate in diagnose_incident (61)`.

### Task 8: E2E script (73)

**Files:** Create `scripts/report_incident.py` + sample `artifacts/incidents/<id>/` (packet/card/dossier JSON+MD); test determinism (template path byte-identical reruns).
**Interfaces:** Consumes Tasks 1, 7. Produces artifacts consumed by Task 9.

- [ ] Step 1 (RED): Failing determinism test (same seed → byte-identical packet + card).
- [ ] Step 2 (GREEN): Implement diagnose → packet+conf+flow → tev-or-template → card/dossier; offline, no bridge changes.
- [ ] Step 3: Commit `feat: report_incident e2e (73)`.

### Task 9: React diagnosis UI (67, 68, 66-banner)

**Files:** Create `frontend/src/diagnosis/{types.ts,parse.ts,DiagnosisCard.tsx,DossierView.tsx,AbstainBanner.tsx,DiagnosisLoader.tsx}` + `frontend/src/test/diagnosis-smoke.spec.ts` (recorded fixture); Modify `MachinePanel.tsx` (section below CausalProofCard, passthrough props), `NarrationBar.tsx` (optional abstainNotice line), `SimPage.tsx` (loader state), `docs/FRONTEND.md`.
**Interfaces:** Consumes Task 8 artifacts (packet v1 IDs, card claims, dossier). Additive, default-off.

- [ ] Step 1 (RED): Vitest — rendered chip IDs ⊆ packet ID universe; abstain shows reason+coverage with zero chips; same JSON → same HTML.
- [ ] Step 2 (GREEN): Implement panels reusing CausalProofCard onSelect/onStepTo; evidence chips carry IDs; click steps cursor. `npm run gates` fully green (palette/scope/tsc/vitest/a11y/perf).
- [ ] Step 3: Commit `feat: diagnosis panels in /sim (67/68)`.

### Task 10: LLM phrasing (71)

**Files:** Create `src/phrase.py` (two-stage: extractor copies numbers/IDs, LLM rewrites prose only, verifier diffs) + fixture tests (schema/IDs-subset/numbers-diff, offline).
**Interfaces:** Consumes Tasks 6/9 (template baseline + fixtures). Template always default; Ollama open-schema behind flag + p95 ≤8s gate.

- [ ] Step 1 (RED): Failing fixture tests (invented number → fallback; unresolvable citation → fallback).
- [ ] Step 2 (GREEN): Implement; kill on any invented number (ship template only).
- [ ] Step 3: Commit `feat: constrained phrasing (71)`.

### Task 11: Ship proof (gates, 0-diverge, Linear)

**Files:** Record-only (docs + Linear updates).
- [ ] Re-run T12 gates + bridge suite + battery gates + 5× same-seed 0-diverge proof + held-out seed confirmation of tuned points.
- [ ] Update all 15 Linear issues with measured evidence; close 65/70/docs; final whole-branch review; then merge/PR decision with user.

## Parallel order

Serial per SDD (one implementer at a time, review per task). Order: 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10 → 11. Tasks 3/4 are compute-heavy runs and may overlap wall-clock with Task 2 analysis — still one writer at a time.
