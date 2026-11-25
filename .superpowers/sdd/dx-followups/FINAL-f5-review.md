# FINAL-f5-review — final gate review of `assert_delay_starved_mass` (READ-ONLY + test re-run)

Worktree: `m0b-t-build`. Scope per gate brief: (1) review `git diff src/possibility.py`
(the ONLY code change; `tests/test_possibility.py` and `probe_delay.py` belong to the
still-open original lane — NOT touched, no edits made by this review); (2) re-run the
3-file pytest command and record exit code + counts. No code edits, no commits, no Linear.

## 1. Diff under review

`git diff src/possibility.py` = single hunk `@@ -377,3 +377,37 @@`, **+34 lines, 0 deletions**
— additive-only, appended after `rank_nodes`. New symbol only:
`assert_delay_starved_mass(injected, starved, n_downstream, buffer_shield_steps=0.0) -> dict`.
No other `src/` change. (`git status` also shows `M tests/test_possibility.py` +
`M probe_delay.py` untracked/probe files — original-lane property, out of scope, untouched.)

Logic: `n_downstream == 0 → {"ok": True, "side": "vacuous"}` first; then
`starved > injected * n_downstream → AssertionError("CONSERVATION: ...")`; then
`starved < injected - buffer_shield_steps → AssertionError("VISIBILITY: ...")`;
then `buffer_shield_steps > 0 and starved < injected → shielded`; else `visible`.

## 2. Spec compliance vs tests/test_possibility.py lines 71–117 (5/5 exact)

| Test | Inputs | Expected | Impl behavior | Pass? |
|------|--------|----------|---------------|-------|
| T1 holds_on_visible (71–78) | (4, 6, 2), shield 0.0 | `ok is True` (6 ≤ 4×2=8; 6 ≥ 4−0) | conservation 6>8 F; visibility 6<4 F; shield 0 → `{"ok":True,"side":"visible"}` | YES |
| T2 rejects_starvation_from_nothing (81–88) | (2, 9, 2) | `pytest.raises(AssertionError, match="CONSERVATION")` | 9 > 2×2=4 → raises `CONSERVATION: starved=9 exceeds injected=2 x n_downstream=2`; `re.search("CONSERVATION")` matches | YES |
| T3 flags_buffer_decoupled (91–100) | (6, 1, 2, shield=0.0) | `pytest.raises(AssertionError, match="VISIBILITY")` | conservation 1>12 F; visibility 1 < 6−0 → raises `VISIBILITY: starved=1 below injected=6 - buffer_shield_steps=0.0`; match OK. Order correct (conservation first, no conflict) | YES |
| T4 shielded_delay_passes (103–108) | (6, 1, 2, shield=6.0) | `ok is True and side == "shielded"` | 1>12 F; 1 < 6−6=0 F; shield 6>0 and 1<6 → `{"ok":True,"side":"shielded"}` | YES |
| T5 vacuous_without_downstream (111–117) | (6, 0, 0) | `ok is True and side == "vacuous"` | `n_downstream == 0` early-return before both legs → vacuous | YES |

Check-order note: for n≥1 and shield≥0 the two fences cannot both fire
(`injected*n ≥ injected ≥ injected−shield` for non-negative inputs), so
conservation-first ordering is unambiguous on all 5 pins. No boundary
(`==`) case is exercised by the 5 tests; `>`/`<` strictness matches the
sketch and all pins have margin ≥1.

**Spec verdict: 5/5 compliant — exact messages (`CONSERVATION`/`VISIBILITY`
keywords), exact `AssertionError` type, exact `ok`/`side` return shapes.**

## 3. Code quality / file-style fit

- Fits file idiom: module docstring + `from __future__ import annotations`,
  typed signature, plain-`dict` return, f-string messages, no new imports.
- Docstring states both legs and the vacuous rule — matches module's
  explanatory-docstring convention.
- Known deviation (NOTED, not blocking — see §5 naming): this is the first
  `raise` in `src/possibility.py` (previously raise-free per FINAL-f5-style)
  and the first `assert_`-prefixed, dict-returning validator in `src/`.
  The deviation is **spec-mandated** (tests require the raise + `ok`/`side`
  envelope), so conforming to file style here would break spec compliance.
- No dead code, no mutation of inputs, multiplicative (zero-safe) conservation
  form — no division anywhere, consistent with the H2 constraint.

## 4. Test re-run (record)

Command (as briefed):
`python -m pytest tests/test_possibility.py tests/test_battery_v2.py tests/test_calibration_gate.py -q -p no:cacheprovider`
with `$env:PYTHONPATH='C:\Users\athma\AppData\Local\Temp\opencode\pycompat;<worktree>'`

- **Exit code: 0**
- **23 passed, 1 warning** (warning = pre-existing `calibration_artifact.py:42`
  UserWarning on unreadable artifact in `test_calibrator_artifact_roundtrip`;
  unrelated to this diff).
- `tests/test_possibility.py` contains 9 `def test_` (4 pre-existing + 5 F5);
  zero failures overall ⇒ **test_possibility 9/9**, confirming the claimed 9 passed.

## 5. Advisory grading (BLOCKING vs NOTED)

1. **Naming (FINAL-f5-naming: needs-rename)** — `assert_` prefix returns a dict
   and raises `AssertionError`, vs repo convention (`assert_* → None`,
   `raise ValueError`). **NOTED, not blocking.** The tested contract
   (lines 71–117) *requires* this exact name, exception type, and return
   envelope; renaming or switching to `ValueError` would fail T2/T3/T4/T5.
   Correct disposition: land as-is for the open lane; any rename is a
   follow-up owned by the original lane with its tests.
2. **Num H1 — float-vs-int wiring hazard (PRESENT, latent).** **NOTED, not
   blocking.** Lives at the probe→gate wiring boundary (`probe_delay.py`
   throughput floats), not in this diff; all 5 pins are exact ints and
   cannot misfire. No `int()`-truncation or float substitution exists in
   the implementation.
3. **Num H2 — division-by-zero (ABSENT).** **NOTED (satisfied).** Implementation
   keeps the zero-safe multiplicative form and orders the vacuous
   early-return first. Constraint for future edits: do not refactor to
   per-machine averaging.
4. **Num H3 — epsilon tolerance (PRESENT for production wiring; ABSENT for
   the 5 pins).** **NOTED, not blocking.** Omitted `tol=1e-9` flips none of
   the 5 outcomes (margins ≥1); adding it now would be untested scope creep
   beyond the pinned spec. Revisit only when float wiring lands, per the
   report's own scoping (window bias ≠ representation noise).
5. **Spec 2/5 synthetic (FINAL-f5-spec)** — shielded-pass has no stocked-buffer
   episode (max observed bufq 2.0 < 6.0); vacuous-pass has no sink-origin
   episode; the other three are scaled analogues (injected 4/6/2 < observed
   dur 9–12). **NOTED, not blocking.** The tests are gate-*logic* pins, and
   the advisory itself recommends keeping all five (marking 4–5 logic-only).
   Nothing in the implementation misrepresents them as episode replays.
6. **Testqual sufficient (FINAL-f5-testqual)** — 5 tests form a minimal cover
   (all five mutant classes killed; T1 side-check and boundary inputs listed
   as optional hardening only). **NOTED (positive).** No action required.

**Blocking count: 0.**

## Verdict: GO (commit-ready)

`src/possibility.py` +34 additive-only diff is spec-compliant 5/5 with exact
messages/behavior, stylistically consistent except where the spec itself
mandates otherwise, and the suite re-runs green (**exit 0, 23 passed**,
test_possibility 9/9). All filed advisories grade NOTED; none blocks.
Suggested commit scope for the owner: `src/possibility.py` only
(tests/probe remain original-lane property).
