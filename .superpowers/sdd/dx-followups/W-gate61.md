# W-gate61: calibration gate obs-only audit (Shreyas F16/F20, PRISSUE-61)

## Verdict: CLEAN — no violation, no fix, no refit

Temperature scaling + Platt inputs and the margin they validate on are
obs-driven only. `stale_hold_run` / `reject_flag_count` (GT-anchored) feed
neither the fit nor the serve path of the calibration gate.

## Trace (margin computation back to features)

Serve (`src/diagnose.py:390-399`, gate section only):
`diagnose_incident` → `rank_nodes(evidence)` → `probs` →
`calibrated_conf(probs, T, a, b)` → `scaled_margin` = top1−top2 of
T-scaled probs → Platt `P(correct|margin)`. Gate-only: rank/order untouched;
below `tau` → `abstain: low-confidence-calibrated` through existing path.
`evidence[m].score` = injected `scores[m]` or `_eweight` fallback
(`onset_kind`/`own_state` heuristic, :357-366) — no counter columns.
`diagnose.py` contains zero references to `stale_hold_run` /
`reject_flag_count` / `down_run` (grep-verified).
`scores=` producers (`scripts/report_incident.py:measure_scores`) use max
`|prefix-z|` over obs channels only — obs-derived, same role as stage-2.
Onsets (`machine_onset`) use `obs_*`, `state_*`, and per-machine `tputlag_*`
(uniform per-machine counters, not root-anchored) — no banned columns.

Fit (`scripts/fit_calibration.py:44-55`): margins from teacher window probas
`P = oof[proba_*]` in `artifacts/oof_identity.parquet`; Platt `(a,b)` fit on
non-held fault windows, `tau=0.739` frozen, VERIFY transfer on exclude-held
held-5. GT is used only as the correctness label (`pred==root`), which is
required for calibration — banned columns are not features.
Teacher features (`X_identity`, shape `(96000, 134)` = 5×26 obs stats +
2×2 struct stats) built with `OBS_STRUCT_COLS = (cycle_lag,
degrade_flag_count)` — the banned pair is excluded by construction
(`src/window_dataset.py:24-30`; width 134 proves it: banned-four would be
138). Shipped artifact `artifacts/calibration.json`: T=2.58, a=6.4202,
b=−2.7236, tau=0.739 frozen, verify risk 0.044 ≤ 0.3 budget, n=8582,
verdict SERVE — untouched, no refit needed.

Adjacent note (out of scope, not the calibration gate): `src/sensor_process.py`
`quality_lift` reads `reject_flag_count` for the D2 sensor/process verdict —
it never enters T/Platt/margin. Flagged for the owning lane, not changed here.

## Changes

- Added `tests/test_gate_obs_only.py` (5 tests): struct-cols exclusion,
  window-feature poison immunity (byte-identical X), gate conf + abstain
  poison immunity (999-valued banned cols change nothing), fit/gate-section
  source-absence guard.
- No changes to `src/diagnose.py`, no artifact refit (`artifacts/calibration.json`
  byte-identical).

## Tests + exit codes

- TDD: new tests GREEN on clean tree (5 passed); RED demonstrated by
  in-memory mutation (patched `OBS_STRUCT_COLS` += banned pair → guard fails
  naming the leak: `{'stale_hold_run', 'reject_flag_count'}`; no files touched).
- Gate suite: `test_gate_obs_only + test_calibration_gate + test_gates +
  test_hybrid_gate + test_twin_gates` → 43 passed, 1 failed (exit 1).
  The single failure (`test_twin_gates::test_quarantine_no_banned_strings`,
  torch-token grep over `src/`) is pre-existing and unrelated — reproducible
  standalone, in files outside this lane's scope, unaffected by this change.

## Numbers

- Teacher width 134 (not 138) ⇒ banned cols absent from fit features.
- Served artifact verify: coverage 0.232 @ tau=0.739, risk 0.044 (budget 0.3),
  n=8582, SERVE. Poison (999) on banned cols: Δroot=0, Δconf=0, Δabstain=0.
