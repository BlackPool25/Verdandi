# W-docs69 — review-context audit fixes (PRISSUE-69: F13/F17/F19 + void sources)

Branch: `m0b-t-build`. Scope: read-only audit + doc fixes, no code/tests/scripts/artifacts touched.
No Linear writes. Context7 unavailable; PR identity resolved via public GitHub API (read-only).

## (1) Void / superseded sources — SHIP_STATUS.md + PROJECT_REPORT.md: CLEAN

Grep over both files for `0.963|0.854|0.987|0.685|collision|PR#31|PRISSUE-31|single-origin`:
- No citable occurrences. The v1 single-origin 0.963 and PR#31 collision-battery
  numbers do not appear as evidence anywhere in either file.
- SHIP_STATUS struck ledger correctly names only leak-contaminated strikings
  (identity 0.606, stacked 0.608/0.610, dense retrieval 1.000) with lineage.
- PROJECT_REPORT §3 VOIDED paragraph correctly scopes the same set; clean identity
  0.674 stands; frozen-v7 exposure bounded −3.4pp.

Flagged (outside owned files, correctly labeled non-citable — no action taken):
- `docs/WINDOW_GBM_V1_MODEL_CARD.md:55` — v1 0.963 labeled "superseded reference",
  "does not transfer". Must never be promoted to citable evidence.
- `docs/NEXT_AGENT_BRIEF.md:63` — "A0-only 0.963 (origin memorization)" in a
  killed-alternatives context. Same disposition: do not cite.
- PR identities (public API): PR #29 = v1 0.963 source (merged, 48 files);
  PR #30 = window-GBM v2 multi-origin w=128 (closed UNMERGED, 48 changed files);
  PR #31 = v2 follow-up (merged, 10 files); PR #32 = "collision-free battery +
  tradeoff" (merged, 3 files — the superseding valid-numbers PR).

Fix applied: `ARCHITECTURE_JEV.md` §4 eval baseline `0.671` → `0.671 pre-regen
baseline (0.654 rerun; PROJECT_REPORT.md §3)` — the 0.671 value was the only
pre-regen number cited without lineage in owned docs.

## F13 — v6 digest references: explicitly unpinned

- Owned docs cite no v6 digest values at all (verified by grep for
  digest/sha256/v6 in SHIP_STATUS, PROJECT_REPORT, ARCHITECTURE_JEV,
  PROJECT_ARCHITECTURE — only generic `replay_digest`/schema-v6 mechanism refs).
- `docs/SIM_SPEC.md:27-28,264-265` already marks v6 digests explicitly unpinned
  pending PRISSUE-30 re-measurement ("no v6 replacement digest is pinned here
  until measured"). Compliant, not missing.
- Fix applied: `PROJECT_REPORT.md` §3 now states "v6 digests: none pinned in this
  report … explicitly unpinned, not missing" with the SIM_SPEC pointer.

## README counts stale — fixed in owned doc, README annotated not edited

- README §Testing claims "300+ tests across 34 files" — stale, predates branch.
- Measured 2026-11-25: 116 `test_*.py` files, 696 `def test` functions
  (`Select-String`; pytest-collected count may differ from grep count, which
  explains variance vs the 108 files/628 tests estimate — method, not substance).
- Fix applied: `PROJECT_ARCHITECTURE.md` §11 now carries the measured counts with
  method + a stale-note on README §Testing. README itself untouched (not in
  owned-file set; owner to refresh or accept annotation).

## F17 — PR#30-only files vs main: ZERO remain; full inventory + disposition

PR #30 (BlackPool25/Verdandi#30, "Window-GBM v2: multi-origin w=128", closed
unmerged 2026-11-08; head `6f20a47`): 48 changed files = 39 added + 9 modified.
Verified each of the 39 added against `origin/main` (`git ls-tree`): ALL 39 ARE
PRESENT on main — the content landed via follow-up merges (incl. merged PR #31).
So the PR#30-only-vs-main set is EMPTY; "~30" matches nothing on current main
(closest sets: 39 added-at-the-time, 25 non-test added, 19 branch-modified —
all reported here for traceability).

39 added (all on origin/main; disposition):
- docs (5): M0B_HYPOTHESIS_REGISTRY.md, M0B_PREREG_AMENDMENT_VUS.md,
  M0B_S5_DELTAS.md, WINDOW_GBM_V1_MODEL_CARD.md (carries void v1 0.963 as labeled
  superseded ref — DO NOT CITE), m0b_battery_supplement.json — process/lineage
  docs, keep; MODEL_CARD numbers struck from citable record.
- root (2): h5-calibration-runtable.csv, m0b-train-runtable.csv — run tables,
  superseded by frozen-battery lineage; keep as history.
- scripts (11): adjudicate_h_wires.py, bench_windows.py, expand_m0b_battery.py,
  export_m0b_v6.py, finalize_window_model.py, gen_mass_battery.py,
  m0b_vus_appendix.py, measure_cusum_p0.py, sweep_window_gbm.py,
  train_tabular.py, train_windows.py — v1/v2 window pipeline; superseded by
  frozen `m0b_mass` battery + Task 2–5 reruns; keep as history, not evidence.
- src (7): apply_calibration.py, calibrate_3arm.py, fusion.py, oof.py,
  step_dataset.py, vus_pr.py, window_dataset.py — same disposition as scripts.
- tests (14): test_adjudicate, test_apply_calibration, test_bench_windows,
  test_calibrate_3arm, test_expand_battery, test_export_m0b_v6,
  test_finalize_model, test_fusion, test_mass_windows, test_oof,
  test_step_dataset, test_train_tabular, test_vus_pr, test_window_dataset —
  cover superseded pipeline; keep green, not ship evidence.
9 modified in PR #30 (.gitignore, run_m0b_baseline.py, detect.py, gates.py,
train_pipeline.py, test_detect.py, test_gates.py, test_m0b_baseline.py,
test_train_pipeline.py) — all on main by definition; 5 of the 48 PR#30 files
evolved further on this branch vs origin/main (finalize_window_model.py,
gen_mass_battery.py, train_windows.py, window_dataset.py,
test_window_dataset.py) — that delta is current-batch work, not PR#30-only.

## F19 — 700-seed manifest checksum: pinned file-level, recorded why not embedded

- `docs/m0b_mass_v2_full_{off,on}.json` (700 fault + 300 clean/arm, seed-identical
  full-mix grids behind the v2 0.719-vs-0.680 claim) carry NO embedded
  sha256/checksum key — their generator scripts emit none (only
  `scripts/freeze_m0b_battery.py` emits sha256, for `m0b_battery_manifest.json`).
  Manifests are branch-committed docs; regenerating them to embed a checksum is
  out of scope for this docs-only task.
- Fix applied: file-level sha256 (computed 2026-11-25, 64-hex verified) pinned in
  `SHIP_STATUS.md` v2-claim row:
  off `a076ed0df107cf93c3a1e8daf8fac53b6cefa18febd07b437d5675e5b954a518`,
  on `958c0b8c4da0ada005f7d98f477ad62c112f0e8f17d24106168ed8c309da5258`,
  with "generator emits none" recorded as the why-not.

## Files changed (this commit)

- `docs/SHIP_STATUS.md` — v2 row: manifest sha256 pins + why-not.
- `docs/PROJECT_REPORT.md` — §3: v6-digest unpinned statement.
- `docs/ARCHITECTURE_JEV.md` — §4: 0.671 → pre-regen with rerun lineage.
- `docs/PROJECT_ARCHITECTURE.md` — §11: measured test counts + README stale note.
- `.superpowers/sdd/dx-followups/W-docs69.md` — this report (new).
