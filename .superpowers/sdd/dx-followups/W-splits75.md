# W-splits75 — calibration-split stratification (F12) + embargo status (F9)

PRISSUE-75 follow-up. Scope: `scripts/eval_stacked.py` split/CV code only
(ranker objective/params untouched; `diagnose.py`, `frontend/*`,
`report_incident.py` untouched; no Linear writes).

## F12 verdict: PASS (verified, no fix needed in owned scope)

- `scripts/eval_stacked.py::_lambdarank_cv` already splits via
  `StratifiedGroupKFold(n_splits=3)` with family as stratum and episode as
  group (`cv.split(X, famids, groups)`). Not every-3rd, not order-dependent.
- Refactor (behavior-identical): extracted `_episode_folds(groups, fam)` helper,
  now used by `_lambdarank_cv`; same sklearn call, same arguments → fold
  assignments and all downstream numbers unchanged → **no calibration re-run**.
- New regression lock: `tests/test_stacked_splits.py` (3 passed; 12 neighboring
  tests in `test_stage2_oof` / `test_stacked_onsets` / `test_stacked_votefree` /
  `test_ranker_calibration` also green).
- Ranker T/Platt fit/eval split (`fit_ranker_calibration.split_episodes`) is
  likewise fam-stratified 50/50, seed-pinned — verified by reading.
- **Flagged, not fixed (out of write scope):** `scripts/finalize_window_model.py:69`
  `cal_eps = set(eps[2::3])` IS order-dependent every-3rd-episode with no family
  stratification. Recommending its owner switch to a fam-stratified episode split;
  that change WOULD move window-GBM calibration numbers and needs a re-run with
  n/seed/lineage recorded.
- Caveat noted (pre-existing, unchanged): `famids` uses salted `hash(f)`, so
  exact fold assignment can vary across processes; within a run stratification
  and grouping hold. Stable label-encoding left for a follow-up since it could
  move numbers.

## F9 embargo status: NONE REQUIRED

- `src/window_dataset.py::build_windows` groupbys `episode_id` and slides
  `g.iloc[s:s+w]` strictly inside one episode — no window spans episodes.
- Stride-8 overlap is therefore intra-episode only; episode-grouped folds share
  zero windows/samples. Ranker rows are per-(episode, machine) aggregates, one
  further remove from window overlap.
- Transfer claims (`exclude-held5` retrain, held-5 gate) train on non-held
  episodes and report on held-5 episodes — episode-disjoint by construction.
- Recorded as a code comment in `_lambdarank_cv`, a note in
  `docs/DIAGNOSIS_QUALITY.md` (Transfer section), and
  `test_windows_never_span_episodes` in `tests/test_stacked_splits.py`.

## Commit

None — worktree shared with other agents' uncommitted changes; my files
(`scripts/eval_stacked.py`, `tests/test_stacked_splits.py`,
`docs/DIAGNOSIS_QUALITY.md` note, this report) left uncommitted for owner to
pick up.
