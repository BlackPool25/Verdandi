# FINAL-dqcomplete — DQ record-per-lane read-only check (2026-11-25)

Worktree: `m0b-t-build` (Verdandi). Source of truth read: `docs/DIAGNOSIS_QUALITY.md` (296 lines, working tree).
Registry: `.superpowers/sdd/dx-followups/progress.md`. Lane reports: `.superpowers/sdd/dx-followups/W-*.md`.
No DQ edits, no commits, no tests, no Linear writes (read-only lane).

Result: PRESENT 5 / MISSING 5 (of 10 required; 1 missing is expected-pending active lane F5).

## PRESENT (DQ entry with measured numbers exists — quotes below)

### 1. splits+embargo (F12/F9) — PRESENT (structural, no numeric metric by nature)
- DQ `docs/DIAGNOSIS_QUALITY.md:280-289` ("Split integrity (2026-11-25, PRISSUE-75 F12/F9)"):
  - "ranker CV (`scripts/eval_stacked.py::_episode_folds`) is family-stratified episode-grouped (StratifiedGroupKFold, every family in every fold — verified by `tests/test_stacked_splits.py`)"
  - "ranker T/Platt fit/eval split is likewise fam-stratified (`fit_ranker_calibration.split_episodes`)"
  - "NOTE for owner of `scripts/finalize_window_model.py:69`: its `cal_eps = set(eps[2::3])` is order-dependent every-3rd-episode, NOT family-stratified — out of scope here, flagged not fixed"
  - "Embargo: NONE REQUIRED — windows are built strictly within episodes (`build_windows` groupbys `episode_id`), so stride-8 overlap is intra-episode only and episode-disjoint folds share zero samples."
- Lane `W-splits75.md`: F12 PASS (helper-extracted `_episode_folds`, same sklearn call, no number change → no calibration re-run); `tests/test_stacked_splits.py` 3 passed + 12 neighboring green; F9 NONE REQUIRED (same intra-episode argument). Note: lane left changes uncommitted (shared worktree) but the DQ note IS present in the working-tree DQ.

### 2. onset grid (F17) — PRESENT
- DQ `docs/DIAGNOSIS_QUALITY.md:228-258` ("Onset/delay grid audit (MEASURED 2026-11-25, W-onsetgrid, seed=0)"):
  - "Delay: `scripts/bench_windows.py:142` rebuilt the stream at hardcoded w=32 (v1 grid) while the shipped detector grid is w=128/stride 8 … Fixed: stream grid now resolves from the artifact's own `model.joblib` w/stride"
  - "Onset: `scripts/evaluate_localize.py:35,43-44` hardcodes w=128/stride-8/center-64 … artifact grid already. … Locked by `tests/test_onset_grid.py::test_evaluate_localize_is_w128_grid`"
  - Corrected table (`scripts/eval_localize.py`, frozen `artifacts/window_cache`, 96000 w128/s8 windows, 4800 eps; HistGBM(300)+sigmoid, train 3200 eps / held-out 1600 eps [1400 fault + 200 clean]; thresholds global-maxF1=0.602, score med pos/neg 0.700/0.475 (n=15735/16265)):
    - "global 0.8 (locked) | delay p50 0 | max 128 | pre-fault-fire 0.00 | fired 739/1400 | missed 661/1400"
    - "global 0.5 | p50 −32 | max 144 | pre-fault-fire 0.65 | missed 1/1400"
    - "per-family tuned | p50 0 | max 32 | pre-fault-fire 0.49 | missed 11/1400"
  - "Delay def: (first firing window − first fault-overlap window) × 8 (`bench_windows.stream_delays`); negative = clean-window fire ahead of the fault"
- Lane `W-onsetgrid.md`: same numbers; `test_onset_grid` (3) + bench/localize/onset suites = 13 passed.

### 3. norm compare (F21) — PRESENT
- DQ `docs/DIAGNOSIS_QUALITY.md:35-56` ("Norm-matched family comparison (MEASURED 2026-11-25, W-normfam, seed=0)"):
  - "2x2 OOF rerun … on the same seed-pinned 240 episodes (24/family + 72 clean) of the dense-cut battery (`artifacts/m0b_mass_c*.parquet`, w=128/stride-8 invariant-23, n=4800 windows, 3-fold episode-grouped CV)":
    - "binary (fault vs window) | 0.7773 | 0.7773 | 0.0000"
    - "multiclass (8-class, fault = pred != none) | 0.7645 | 0.7645 | 0.0000"
  - "Matched gaps: multi−binary = −0.0128 under clean norm and −0.0128 under all norm (published confounded gap −0.051 same sign)"
  - "Multiclass attribution still collapses on obs families under matched norms (bias 0.303 / drift 0.048 / quality 0.066 / spike 0.075 vs breakdown 0.796 / loss 0.929)"
  - "Verdict: the family-capped conclusion SURVIVES … Lineage: `artifacts/eval_family_norm.json` (episode_ids listed, seed=0)"
- Lane `W-normfam.md`: same table + per-family binary recall (breakdown 0.982 / delay 0.939 / loss 0.946 / spike 0.613 / bias 0.588 / quality 0.496 / drift 0.329); 5 tests passed.

### 4. shuffle (62) — PRESENT
- DQ `docs/DIAGNOSIS_QUALITY.md:113-133` ("Criteria-order shuffle (MEASURED 2026-11-25, PRISSUE-62, n=60 seed=0)"):
  - "| fixed | 0.113 (6/53) | 0.132 (7/53) | 0.000 | 53 |"
  - "| shuffled (order-seed=1) | 0.113 (6/53) | 0.170 (9/53) | 0.000 | 53 |"
  - "Fixed-arm gated SC (machine-only, 5 votes): 0.113 — unchanged, still < 0.3. Shuffled-arm gated SC: 0.094 — also < 0.3."
  - "Machine score identical under shuffled option order … Family +0.038 under shuffle is noise at n=53, still << teacher."
  - "Verdict: **KILL stays** (0.113 << 0.671; kill lifts only at machine ≥ 0.671)."
  - "Logs: `artifacts/tev_shuffle62_fixed.log`, `artifacts/tev_shuffle62_shuffled.log`"
- Lane `W-shuffle62.md`: identical table (seed 0, order-seed 0/1); 17/17 `test_eval_tev.py` green; committed aec4cec + 4c07b7b.

### 5. judge top-up (72) — PRESENT
- DQ `docs/DIAGNOSIS_QUALITY.md:135-162` ("Template faithfulness (MEASURED 2026-11-25, n=60 seed=0)"):
  - "| template citation precision | undefined (0 non-abstain cards) | 0/60 |"
  - "| template slot recall | undefined (0 non-abstain cards) | 0/60 |"
  - "| template per-claim recall (required-cited/required) | undefined (0 non-abstain cards) | 0/60 |"
  - "| template trace-coverage recall | undefined (0 non-abstain cards) | 0/60 |"
  - "| abstain rate | 1.000 (60/60) | 60 |"
  - "| NLI faithfulness | SKIPPED (no local MNLI model) | — |"
  - "Pairing rule (2026-11-25): precision/recall are only emitted via `scripts/eval_jev.py::format_report`, which always appends `abstain_rate` — enforced by `test_precision_never_reported_without_abstain_rate`"
  - "Lineage: `src/faithfulness.py` (`NliUnavailable`-gated 3-run x 2-order aggregator, flip-kill 0.20; `claim_recall` fractional required-cited/required slice …); Fixture recall is 1.0 by construction"
- Lane `W-judge72.md`: added `claim_recall` + `format_report` abstain-pairing; 27 passed / 2 skipped (key/model-gated); NLI still deferred (no weights/torch, no downloads).

## MISSING (no DQ entry for the lane's measured numbers — lane quotes for controller)

### 6. gate input-shape (F16/F20) — MISSING
- Lane `W-gate61.md` measured (no DQ edit made by lane; Changes list tests only, no DQ touch):
  - "Teacher width 134 (not 138) ⇒ banned cols absent from fit features" (`OBS_STRUCT_COLS = (cycle_lag, degrade_flag_count)`, width 134 proves exclusion; banned-four would be 138)
  - "Served artifact verify: coverage 0.232 @ tau=0.739, risk 0.044 (budget 0.3), n=8582, SERVE" (`artifacts/calibration.json`: T=2.58, a=6.4202, b=−2.7236, tau=0.739 frozen)
  - "Poison (999) on banned cols: Δroot=0, Δconf=0, Δabstain=0"
  - Gate suite: 43 passed, 1 failed (pre-existing unrelated `test_twin_gates::test_quarantine_no_banned_strings`)
- DQ grep: no `134`/`138`/`0.232`/`poison`/`obs-only`/`OBS_STRUCT` hit (only `tau=0.044` window-transfer and `1389/1400` table hits). Existing T=2.58 window-transfer rows (DQ:260-279) are NOT the gate-shape audit. Needs a DQ note with the three bullets above.

### 7. STARVED-mass probe (F5) — MISSING (expected-pending: lane still active)
- No lane report file: `.superpowers/sdd/dx-followups/W-f5assert.md` does NOT exist (glob confirms).
- Registry `progress.md:25-28`: "F5 mid-TDD-RED (`assert_delay_starved_mass` not yet implemented — healthy, hands off)", "Only F5 remains active", "FINAL-10 … F5 still RED/active, its 3 files off-limits for writes".
- DQ grep: no `STARVED`/`starved`/`assert_delay` hit. DQ "Path teleport (64)" (`DIAGNOSIS_QUALITY.md:70-84`: `flow_teleport` α=0.85, ranked 0.072/0.287/1.8 both arms, Δ+0.000 diagnostic-only) is PRISSUE-64, NOT the F5 STARVED-mass probe — not a substitute.
- Disposition: expected-pending; DQ entry correctly absent until F5 goes GREEN + commits.

### 8. measured E2E (66) — MISSING (lane explicitly deferred the DQ insert)
- Lane `W-e2e66.md` measured (seed-pinned, live `diagnose_incident` + served tau=0.739, oracle trigger, gate-conditional):
  - seed 0 (n=200): "coverage 0.015 (3/200) | selective-acc 0.333 (1/3) | risk 0.667 | abstain 112 single-node / 39 silent-clean / 46 low-conf-cal"
  - seed 1 (n=200): "coverage 0.025 (5/200) | selective-acc 0.800 (4/5) | risk 0.200 | abstain 121 / 33 / 41"
  - pooled (n=400): "coverage 0.020 (8/400) | selective-acc 0.625 (5/8) | risk 0.375 | abstain 233 / 72 / 87"
  - "Pooled (COMPOSED): 0.800 (retrieval) x 0.020 (gate) = 0.016 coverage @ 0.625 selective-acc"; "Predecessor DERIVED 0.214 coverage @ ~0.70 → STRIKE, SUPERSEDED as E2E"
  - Lane states: "Proposed record insertions (NOT applied — file ownership)" — new `## End-to-end selective` DQ section text ready on request; SHIP_STATUS DERIVED line to be struck/stand-beside (owned by W-docs69).
- DQ grep: no `0.020`/`0.625`/`0.015`/`selective`/`single-node`/`e2e-selective` hit. DQ `## End-to-end pooled` (`DIAGNOSIS_QUALITY.md:202-208`) carries only old "v7 sentinel + heuristic 0.266–0.284" and "frozen sentinel (0.544) + stage-2 0.432–0.436" — pre-E2E rows. Needs the gate-conditional + composed rows.

### 9. naturals rerun (74) — MISSING (numbers live in SIM_BASELINE + lane report, not DQ)
- Lane `W-v2naturals74.md` measured (production-ambient rerun, seed 1, NEW paths only, no frozen-manifest/`twin.py` edits):
  - "Primary (thr 0.7, obs+flow ON vs obs-only OFF): 0.733 > 0.694 BUT cf 0.117 > 0.093 → KEEP condition NOT met nominally … verdict FLIPPED to SCOPE (general 7-family claim NOT confirmed under ambient → SCOPE to quality/loss-only)"
  - "clean-fire ON 19/300=0.063 vs OFF 24/300=0.080: Δ=-0.0167, SE=0.0210, 95% CI (-0.058,+0.025); MDE@80%≈0.059"
  - "Retrieval ON 503/700 vs OFF 476/700: Δ=+0.0386, SE=0.0245, z=1.57, p≈0.12, 95% CI (-0.009,+0.087)"
  - "Gain knobs frozen: row diff OFF↔ON ignoring `extra`: 0"
  - Committed a478def (audit+manifests+SHIP_STATUS:45 per progress.md); SHIP_STATUS:45 + PROJECT_ARCHITECTURE revert FLAGGED for W-docs69/controller.
- DQ grep: no `0.733`/`0.694`/`0.117`/`naturals`/`ambient` hit. DQ Retrieval section (0.507–0.568 / 0.800 / 0.759) has no naturals-ON/OFF row. Needs a DQ row or pointer to `docs/SIM_BASELINE.md` audit + manifests.

### 10. void-source audit (69) — MISSING as a lane record (pre-existing ledger ≠ audit entry)
- Lane `W-docs69.md` (docs-only; did NOT touch DQ — changed SHIP_STATUS / PROJECT_REPORT / ARCHITECTURE_JEV / PROJECT_ARCHITECTURE + own report):
  - "Grep SHIP_STATUS + PROJECT_REPORT for `0.963|0.854|0.987|0.685|collision|PR#31|single-origin`: No citable occurrences … SHIP_STATUS struck ledger correctly names only 0.606 / 0.608/0.610 / 1.000 … clean 0.674 stands; frozen-v7 exposure −3.4pp"
  - "PR identities: #29 = v1 0.963 source (merged); #30 = window-GBM v2 multi-origin (closed UNMERGED); #31 = v2 follow-up (merged); #32 = collision-free battery + tradeoff (merged, superseding)"
  - "Flagged, correctly labeled non-citable: `WINDOW_GBM_V1_MODEL_CARD.md:55` v1 0.963 superseded ref; `NEXT_AGENT_BRIEF.md:63` A0-only 0.963 killed-alternative — DO NOT CITE"
  - "F13: v6 digests explicitly unpinned (`SIM_SPEC.md:27-28,264-265`); F19: manifest sha256 pinned file-level (off `a076ed0d…`, on `958c0b8c…`, generator emits none); README stale (300+/34) vs measured 116 files / 696 defs"
- DQ `## Voided` (`DIAGNOSIS_QUALITY.md:293-296`) lists "0.606, stacked 0.608/0.610, dense retrieval 1.000 … Clean identity 0.674 … −3.4pp" but contains NO 69-audit record: no 0.963-absence statement, no PR#29–32 identities, no F13/F19 pins. The pre-existing ledger corroborates the numbers the lane verified, but it is not the lane's audit entry.

## Counts
- PRESENT: 5 (splits+embargo F12/F9; onset grid F17; norm compare F21; shuffle 62; judge top-up 72)
- MISSING: 5 (gate input-shape F16/F20; STARVED-mass F5 [expected-pending, lane active]; measured E2E 66; naturals rerun 74; void-source audit 69)
