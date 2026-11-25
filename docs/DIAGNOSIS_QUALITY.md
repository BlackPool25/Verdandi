# Diagnosis quality dashboard (MEASURED only — no projections)

Battery: frozen T=300 (`m0b_mass_*.parquet`, 4200 fault + 600 clean episodes).
Same-battery comparisons only. Lineage per number.

## Retrieval (sentinel)
| config | retrieval | clean-fire | n | bar |
|---|---|---|---|---|
| v7 frozen, thr sweep 0.315–0.8 + 2-of-3 | 0.507–0.568 flat | 0.000 | 4200/600 | — |
| retrained frozen, thr 0.6 + 2-of-3 | **0.800** | 0.032 | 4200/600 | ≥0.75 @ ≤0.05 PASS |
| retrained frozen, thr 0.65 + 2-of-3 | 0.759 | 0.017 | 4200/600 | PASS (tighter) |

Verdict: retrieval bar MET by retraining on the deployment battery (+0.26 over
supplement-trained v7). Threshold sweep is flat — no threshold recovers
quiet families; integration horizon + per-family features are the levers.

## Rerank (attribution given retrieval)
| config | top-1 | n | bar |
|---|---|---|---|
| stage-2 LambdaRank, votable-only | 0.673 | 2665 | ≥0.7 FAIL (gap 0.027) |
| stage-1 majority vote (teacher) | 0.671 | 2665 | — |
| stage-2 pooled (silent count as misses) | 0.455–0.456 | 4200 | — |

Verdict: ranker == teacher (three feature sets, aligned measurement).
Remaining rerank levers: onset/state row features, per-family rankers.

## End-to-end pooled
| config | pooled top-1 |
|---|---|
| v7 sentinel + heuristic rank | 0.266–0.284 |
| frozen sentinel (0.544) + stage-2 | 0.432–0.436 |

Old pooled bar ≥0.5: NOT MET (superseded by decomposed bars).

## Routes (MEASURED 2026-11-11, n=167, same seed)
Heuristic evidence: root-hit@1 0.132 / subseq@3 0.413 / mean-k 1.5.
Ranker evidence (fresh 38-col artifact): root-hit@1 **0.162** / subseq@3 0.413 / mean-k 1.5.
Keep bar: root-hit beats (+0.030, ~noise edge at n=167), subseq ties → **path layer KEPT** (ranker evidence strictly better, no regression) but absolute quality stays diagnostic-only, non-ship.

## Family typing (invariant windows, GroupKFold)
Overall 0.502. breakdown 0.752 / delay 0.753 / loss 0.810 vs bias 0.226 /
drift 0.313 / quality 0.412 / spike 0.247. Provisional: invariant path
keeps frozen struct cols (leak bounded small per v7 ablation).

## Sensor / onset (prior handoff numbers — SUPERSEDED by grid audit below, 2026-11-25)
Sensor top-1 0.26–0.33, onset err ~90 ticks. Process top-1 0.76, onset err 2.0.
SUPERSEDED: grid provenance unverified ("not re-measured here"); tick-level
errors are grid-N/A by construction (sensor stack is tick-level,
`scripts/eval_sensor_stack.py`; ROI head anchors on w128 triggers,
`scripts/train_roi_head.py:36,55-59`) — but the numbers themselves are
un-reproduced handoff claims. Do not cite without the audit row.

## Onset/delay grid audit (MEASURED 2026-11-25, W-onsetgrid, seed=0)
Grid verdict: DELAY claim was on the wrong grid (CONFIRMED); ONSET path was
already on the artifact grid (claim refuted with evidence — no re-measure).
- Delay: `scripts/bench_windows.py:142` rebuilt the stream at hardcoded w=32
  (v1 grid) while the shipped detector grid is w=128/stride 8 (model card v2,
  `scripts/cache_windows.py:65`, all `scripts/eval_*.py`). Fixed: stream grid
  now resolves from the artifact's own `model.joblib` w/stride (`--w/--stride`
  override). The model-card line "Streaming delay: p50 0 ticks" is SUPERSEDED
  (wrong grid, no operating point / n / seed) — corrected below.
- Onset: `scripts/evaluate_localize.py:35,43-44` hardcodes w=128/stride-8/center-64
  with triggers from w128 OOF — artifact grid already. Localizer verdict numbers
  (loss/breakdown |err| 13/15 → calibrated 2/0; delay 123; obs 111-184) stand
  on their grid. Locked by `tests/test_onset_grid.py::test_evaluate_localize_is_w128_grid`.
- Corrected streaming delay, `scripts/eval_localize.py` (new canonical path) on
  frozen `artifacts/window_cache` (96000 w128/s8 windows, 4800 eps; stride
  asserted at runtime; builder lineage `cache_windows.py:64-66`): seed-pinned
  HistGBM(300) + sigmoid calibration, train 3200 eps / report held-out 1600 eps
  (1400 fault + 200 clean; finalize split rule `finalize_window_model.py:68-69`;
  caveat per split audit: every-3rd, not fam-stratified):
  thresholds global-maxF1=0.602, score med pos/neg 0.700/0.475 (n=15735/16265).
  | operating point | delay p50 | delay max | pre-fault-fire frac | fired | missed |
  |---|---|---|---|---|---|
  | global 0.8 (locked) | 0 | 128 | 0.00 | 739/1400 | 661/1400 |
  | global 0.5 | −32 | 144 | 0.65 | 1399/1400 | 1/1400 |
  | per-family tuned | 0 | 32 | 0.49 | 1389/1400 | 11/1400 |
  Delay def: (first firing window − first fault-overlap window) × 8
  (`bench_windows.stream_delays`); negative = clean-window fire ahead of the
  fault ("early-fire on wide windows", now quantified). Note: locked-0.8 p50=0
  matches the old headline numerically but pairs with a 0.47 miss rate on this
  seed/split (card operating table claimed epHit 0.753 @0.8 — gap recorded,
  detector seed unrecorded in card, not reconcilable here).

## Calibration (MEASURED 2026-11-11, teacher OOF windows, n=96000)
T=2.58 (strongly overconfident — consistent with hard-vote findings).
NLL 2.465→1.366, ECE 0.246→0.034 (86% cut, bar was 20%).
Risk-coverage: 0.300@1.0 → 0.249@0.9 → 0.217@0.8 → 0.186@0.7 (monotone).
Module: `src/confidence.py (post-hoc); `src/calibrate.py` (acquisition, pre-existing) (temperature + Platt + coverage gate), 5 tests green.
Ranker-level calibration input: `artifacts/stage2-oof.npz` (saved by `eval_stacked.main`).

## Missing (gates, not numbers)
## Transfer (MEASURED 2026-11-11, teacher windows, T=2.58 calibrated)
| split | forced top-1 | tau (risk≤0.3) | coverage | risk | n |
|---|---|---|---|---|---|
| all windows | 0.700 | 0.080 | 1.000 | 0.300 | 96000 |
| held-5 (ASM1/ASM2/B7P/B9/C6) fault windows | 0.327 | 0.739 | 0.337 | 0.300 | 8945 |

Generalization gap is real (0.70→0.33 forced). The coverage gate converts it
to abstention: on unseen machines it predicts on 34% at the same 0.30 risk.
Open-set retrain (exclude-held training) not run — the reject-by-abstain
behavior above is the shippable half; forced-accuracy transfer is not claimed.
- Per-hop delay calibration: bounds ASSUMED (0,60) pending histogram.
- Cost-weighted metric: deferred per user (accuracy-only bars stand).

## Voided (leak-contaminated, struck from the record)
Identity classifier 0.606, stacked 0.608/0.610, dense retrieval 1.000
(GT-anchored `stale_hold_run`/`reject_flag_count`/`down_run` features).
Clean identity 0.674 stands. Frozen v7 exposure bounded at -3.4pp.
