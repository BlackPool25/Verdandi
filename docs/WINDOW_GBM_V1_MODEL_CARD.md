# Window GBM v1 — model card

Binary fault-vs-clean window classifier (HistGradientBoosting, calibrated) +
per-episode-family max-F1 thresholds. Battery: `m0b-mass-balanced-v1`
(2,000 twin episodes: 1,400 fault across 7 families x 2 rungs + 600 clean;
570,000 rows, step prevalence 2.4%).

## Honest metrics (3-fold GroupKFold OOF, episodes never leak)

- Window-F1: **0.945** (0.5) / **0.963** (per-family thresholds)
- Episode-hit: **1.00**, clean episode FP: 0.015-0.020
- Per-family window recall: breakdown 1.00, loss 0.98, drift 0.96, bias 0.95,
  spike 0.94, delay 0.92, quality 0.88
- Final artifact validation (calibration fold, 666 unseen episodes): window-F1 **0.956**

## Runtime (measured, `scripts/bench_windows.py`)

- Single window: 2.9 ms; batch: ~378k windows/s
- Reload determinism: identical predictions after save/load
- Streaming detection delay: p50 0 ticks, max 0 ticks (onset window)
- Artifact size: 1.8 MB (`model.joblib` + `thresholds.json` + `schema.json`)
- Bench process peak RAM 4.7 GB is dominated by loading the 400 MB
  evaluation shards, not the model.

## Operating thresholds (tuned run)

| slice | threshold |
|---|---|
| bias | 0.0617 |
| breakdown | 0.8688 |
| delay | 0.8309 |
| drift | 0.0678 |
| loss | 0.1641 |
| quality | 0.0592 |
| spike | 0.1291 |
| clean episodes (global fallback) | 0.3787 |

Thresholds were picked on OOF scores: validation numbers, mildly optimistic.
The untuned 0.945 line is the citable headline.

## Killed alternatives (do not revive without new evidence)

- State features (stale_rate/var/slope windows): cut LOF VUS 0.49 -> 0.40.
- In-fold synthetic injection (COE + point outliers): ~zero in-sample gain.
- 16-config GBM sweep: flat landscape 0.905-0.918 on the subset; defaults kept.
- Quality w=64 specialist head: F1 0.0 (sparse signal + imbalance).
- Point-F1 0.90 at 3%: mathematically infeasible (global ceiling 0.645).

## Limits

- Single origin (A0), fixed onset t0=150, fixed episode length 300.
  Solved for one machine, not generally.
- Balanced episode ratio (70% fault) is not a factory profile; step
  prevalence (2.4%) is the honest part.
- No real-plant validation data exists in this repo.
