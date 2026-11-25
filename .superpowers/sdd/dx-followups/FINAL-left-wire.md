# FINAL-left-wire — `assert_delay_starved_mass` wired into `diagnose_incident` candidate #1 (TDD RED→GREEN)

Worktree: `.worktrees/m0b-t-build`. Date (UTC): 2026-11-26.
Scope: candidate #1 ONLY (`src/diagnose.py` upstream-paths trust point). No commit, no Linear.

## 1. Diff (2 files, additive only)

- `src/diagnose.py`
  - New private helper `_delay_starved_inputs(g, root, evidence, edges, kept)` → `(injected, starved, n_downstream, shield) | None`.
  - `diagnose_incident`: import `assert_delay_starved_mass`; gate block between `rank_nodes` and `upstream_paths` (old `:387`); `AssertionError` → early return with existing `low-recall` abstain + `note` carrying the trip message.
  - No signature changes to `upstream_paths`/`rank_nodes`; no gate reordering; no store-write changes; try/except wraps ONLY the assert call.
- `tests/test_diagnose.py` (existing file; no new test files): `_decoupled_delay_df` fixture + 2 tests (trip + family skip).

## 2. TDD RED→GREEN evidence

RED (before wiring, new test only):
`test_delay_starved_mass_gate_abstains_on_decoupled_delay` FAILED —
`assert (None == 'low-recall')`: the decoupled ep-41242-pattern frame
(12 injected `tputlag_C2` steps, 3+3 STARVED steps at C6/C7, empty buffers,
calibrator open) got a confident `root=C2` guess. 14/15 passed.

GREEN (after wiring): `tests/test_diagnose.py` + `tests/test_possibility.py` →
**24 passed**. Gate inputs on the fixture: `(injected=12, starved=6,
n_downstream=2, shield=0.0)` → `6 < 12 - 0` → VISIBILITY trip →
`{root: None, abstain: "low-recall", note: "delay-mass gate tripped:
VISIBILITY: ..."}`.

## 3. Input derivation (steps-to-steps, per FINAL-probeassist §3)

- `injected`: `tputlag_{root}` steps above pre-onset max, counted from root onset to episode end (integer step count, float-typed → C4 safe with strict inequalities).
- `starved`: `state_{m} == STARVED` steps summed over downstream evidence machines reachable from root (transitive BFS over `edges`), same onset-anchored window (C3 documented here).
- `n_downstream`: downstream evidence machines reachable from root (2 for C2→C6/C7; 0 for sinks → committed vacuous leg passes).
- `shield`: queued `buffer_*` cover at `root onset − 1`; `0.0` when no buffer columns.
- Skip (pass-through, `None`) when: no `tputlag_{root}` column (C2 — all existing synthetic frames), no positive injected run, or root onset unknown. Missing data never trips, never `KeyError`.

## 4. Abstain-code decision (parent brief governs)

Parent brief: convert to the existing abstain path, no new codes. Used
`low-recall` — the exact pre-path shape of the `:374-379` empty-evidence
return (`path: []`, `path_prob: 0.0`), since the gate fires before path
enumeration and there is no ranked path to preserve (computing the phantom
path the gate exists to distrust, just to echo it in the dossier, was
rejected as less minimal and less honest).
Deviation from FINAL-left-wirereview §3 (which requires a new code) is
explicit and brief-driven. Its interim allowance is adopted: the return
carries `"note": "delay-mass gate tripped: <CONSERVATION|VISIBILITY ...>"`,
so DQ can disaggregate trip legs inside the `low-recall` bucket.
Downstream-safe, verified: `report_incident.py:40-46` maps `low-recall` →
`abstain_paths`; `:220-221`/`:237` are None-safe on `paths`/`confidence`
(extra `note` key ignored); `eval_e2e_selective` buckets reasons dynamically.

## 5. Review-condition compliance (FINAL-left-wirereview §6)

1. Hunk confined to `diagnose_incident` around `:387` — yes (helper + gate block only).
2. New distinct code — NO (parent brief forbids); interim allowance (note field) satisfied instead.
3. C1 family gate — yes: gate runs only for `fault_family in ("delay", "unknown")`; "unknown" trips only with a positive `tputlag` signature at the top-ranked root (positively identified delay origin). Pinned by `test_delay_starved_mass_gate_skips_non_delay_family` (breakdown → `root=C2`, no trip). C2 missing-column skip — yes. C3 bounded documented window — yes (§3 above). C4 int steps — yes. C5 narrow except — yes.
4. Path preservation — intentionally `[]` (see §4 rationale); never falls through to `build_report`.
5. Wiring tests — trip test + non-delay no-trip test pinned; missing-buffer-columns → `shield=0.0` exercised by the trip fixture (no `buffer_*` columns present); vacuous sink covered by committed `test_delay_starved_mass_vacuous_without_downstream` (helper returns `n=0` → assert passes vacuous).
6. Suite green — yes (§6 below).

## 6. Suite results

FINAL-left-verify 12-file scope + `test_diagnose.py` (13 files):
`test_diagnose test_possibility test_battery_v2 test_calibration_gate
test_gate_obs_only test_stacked_splits test_eval_family_norm test_eval_tev
test_eval_faithfulness test_report_incident test_phrase test_rerank_teleport
test_ranker_calibration` → **110 passed, 1 skipped** (skip pre-existing,
matches FINAL-left-verify baseline 94+1) in ~15s. 1 expected warning
(`test_calibrator_artifact_roundtrip` gate-open UserWarning).
Gate-adjacent extra: `test_pipeline test_eval_e2e_selective
test_oracle_ablation test_report test_incidents test_incident_link` →
**17 passed**.

## 7. Behavior-change statement

Only episodes that (a) carry `fault_family` delay/unknown, (b) show a
positive `tputlag` run at the rank-top root, AND (c) violate
conservation/visibility change outcome (→ `low-recall` + note, no store
writes — same no-row convention as all early abstains, W-minors Minor-3).
All previously-green suites pass unmodified; serve-side E2E lineage on
non-delay families is untouched by construction (C1).

## 8. Constraints honored

No commits (`git status` shows only the 2 intended modified files plus
sibling-lane artifacts I did not touch). No Linear access. Candidate #1
only — `eval_paths.py`, `report.py`, `eval_stacked.py` untouched. Out of
scope, not claimed: offline tuning-loop cleaning (R7), store parity gap
(R8 — extended consistently, not fixed).

## 9. Fix-loop: new distinct code `decoupled-delay` (FINAL-left-wirereview §3)

Date (UTC): 2026-11-26. Reviewer verdict was CONDITIONAL with REJECT on all
existing codes → gate trip now emits `"abstain": "decoupled-delay"`.

- `src/diagnose.py`: gate-trip early return `low-recall` →
  `decoupled-delay` (+ comment updated to cite review §3 + downstream safety:
  `scripts/report_incident.py:247` fallback, `scripts/eval_e2e_selective.py:140-143`
  dynamic bucketing). C1 family gate, C2 missing-column skip, C3 window, C4
  int steps, C5 narrow except — all untouched.
- `tests/test_diagnose.py`: `test_delay_starved_mass_gate_abstains_on_decoupled_delay`
  now asserts `decoupled-delay` (docstring updated); family-skip test unchanged.
- TDD RED-first: new-code test FAILED on old expectation
  (`assert ('low-recall' == 'decoupled-delay')`, 1 failed / 1 passed in
  `-k delay_starved_mass`), then GREEN after the src change.
- Verify GREEN: `test_diagnose + test_possibility` → **25 passed**;
  13-file scope (`test_diagnose test_possibility test_battery_v2
  test_calibration_gate test_gate_obs_only test_stacked_splits
  test_eval_family_norm test_eval_tev test_eval_faithfulness
  test_report_incident test_phrase test_rerank_teleport
  test_ranker_calibration`) → **110 passed, 1 skipped** (skip pre-existing;
  1 expected `test_calibrator_artifact_roundtrip` gate-open warning).
  Gate-adjacent extra (`test_pipeline test_eval_e2e_selective
  test_oracle_ablation test_report test_incidents test_incident_link`) →
  **17 passed**.
- Behavior change vs §7: only delay/unknown + positive `tputlag` + mass
  violation episodes change code (`low-recall` → `decoupled-delay`); the
  committed 233/72/87 `low-recall` histogram bucket is no longer polluted.
- Constraints: no commit, no Linear, no other files touched.
