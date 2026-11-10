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

## Routes (k-best upstream paths, heuristic direction-signature evidence)
| metric | value | n |
|---|---|---|
| root-hit@1 | 0.126 | 167 |
| route-subseq@3 | 0.413 | 167 |
| mean-k (hypotheses) | 1.1 | — |

Note: heuristic evidence, not stage-2 scores. Rerun with ranker evidence
pending. Subsequence >> root-hit: flow shape recovered more often than origin.

## Family typing (invariant windows, GroupKFold)
Overall 0.502. breakdown 0.752 / delay 0.753 / loss 0.810 vs bias 0.226 /
drift 0.313 / quality 0.412 / spike 0.247. Provisional: invariant path
keeps frozen struct cols (leak bounded small per v7 ablation).

## Sensor / onset (prior handoff numbers, not re-measured here)
Sensor top-1 0.26–0.33, onset err ~90 ticks. Process top-1 0.76, onset err 2.0.

## Calibration (MEASURED 2026-11-11, teacher OOF windows, n=96000)
T=2.58 (strongly overconfident — consistent with hard-vote findings).
NLL 2.465→1.366, ECE 0.246→0.034 (86% cut, bar was 20%).
Risk-coverage: 0.300@1.0 → 0.249@0.9 → 0.217@0.8 → 0.186@0.7 (monotone).
Module: `src/calibrate.py` (temperature + Platt + coverage gate), 5 tests green.
Ranker-level calibration input: `artifacts/stage2-oof.npz` (saved by `eval_stacked.main`).

## Missing (gates, not numbers)
- Held-5 transfer table for stage-2: unmeasured (prior: 0.40 classifier).
- Per-hop delay calibration: bounds ASSUMED (0,60) pending histogram.
- Cost-weighted metric: deferred per user (accuracy-only bars stand).

## Voided (leak-contaminated, struck from the record)
Identity classifier 0.606, stacked 0.608/0.610, dense retrieval 1.000
(GT-anchored `stale_hold_run`/`reject_flag_count`/`down_run` features).
Clean identity 0.674 stands. Frozen v7 exposure bounded at -3.4pp.
