# W-onsetgrid (Shreyas F17 on PRISSUE-63) — report 2026-11-25

## Verdict
- **DELAY: grid claim CONFIRMED.** `scripts/bench_windows.py:142` rebuilt the
  stream at hardcoded `w=32` (v1 grid); artifact grid is w=128/stride 8.
  Model-card "Streaming delay p50 0" SUPERSEDED, re-measured below.
- **ONSET: grid claim REFUTED with evidence.** `scripts/evaluate_localize.py`
  hardcodes the w128 grid (starts `arange(0, len-128+1, 8)`, center `trig+64`);
  localizer numbers stand on their grid. Locked by regression test, no
  re-measure needed.

## Corrected numbers (artifact grid, MEASURED, `scripts/eval_localize.py`, seed=0)
Frozen `artifacts/window_cache` (96000 w128/s8 windows, 4800 eps; stride
asserted at runtime). HistGBM(300)+sigmoid, train 3200 eps / report held-out
1600 (1400 fault + 200 clean; finalize `eps[2::3]` rule; every-3rd caveat per
split-audit lane). Thresholds: global-maxF1 0.602; score med pos/neg
0.700/0.475.
- global 0.8 (locked): delay p50 0, max 128, pre-fault-fire 0.00, fired
  739/1400, missed 661/1400 — p50 matches old headline but pairs with 0.47
  miss (card table claimed epHit 0.753 @0.8; detector seed unrecorded, gap
  noted not reconciled).
- global 0.5: p50 −32, max 144, pre-fault-fire 0.65, missed 1/1400.
- per-family tuned: p50 0, max 32, pre-fault-fire 0.49, missed 11/1400.
Delay def = (first firing window − first fault-overlap window) × 8
(`bench_windows.stream_delays`); negative = clean-window fire ahead of fault.

## Changes (mine only)
- `scripts/bench_windows.py`: stream grid resolves from artifact
  `model.joblib` w/stride (+`--w/--stride` overrides); `import resource`
  try/except (win32 `peak_ram_mb=None`) — needed to run/verify on this box.
- `scripts/eval_localize.py` (NEW): canonical grid-asserted delay measurement.
- `tests/test_onset_grid.py` (NEW): artifact-grid pin (RED w=32 → GREEN),
  w128 onset evidence lock, stride-conversion lock.
- `tests/test_bench_windows.py`: 1-line win32 tolerance (was already failing
  pre-change at import).
- `docs/DIAGNOSIS_QUALITY.md`: handoff rows annotated SUPERSEDED + new grid
  audit section with the table above (n/seed/lineage per row).
- `docs/WINDOW_GBM_V1_MODEL_CARD.md`: old delay line annotated, not deleted.

## Verification
`test_onset_grid` (3) + `test_bench_windows` + `test_localize` +
`test_onset` + `test_onsets`: 13 passed. Full re-measure single-process,
seed=0, no battery regen (frozen cache only), no new deps.

## Notes for controller
- `probe_delay.py` (root, untracked) is another lane's ad-hoc probe — read,
  not touched; no collision with my paths.
- `docs/DIAGNOSIS_QUALITY.md` also carries the splits lane's §75 note; my
  edit is adjacent (sensor/onset section), no overlap.
- No Linear writes, no subagents, ≤3 workers (single-process run) per orders.
