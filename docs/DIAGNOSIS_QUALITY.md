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
| RERUN 2026-11-25 seed=0: stage-2 votable-only | 0.667 | 2712 | ≥0.7 FAIL (gap 0.033) |
| RERUN 2026-11-25 seed=0: stage-2 pooled | 0.461 | 4200 | — |
| RERUN 2026-11-25 seed=0: stage-1 majority vote | 0.654 | 2712 | — |

Rerun lineage: battery m0b-mass-balanced-v1 regenerated seed=0 (4200 fault +
600 clean, 48 shards), window cache n=96000, teacher OOF seed=0, onsets ON,
sentinel features OFF (no frozen_oof producer in tree), LambdaRank 3-fold
episode-grouped CV seed=0 deterministic. Input: `artifacts/stage2-oof.npz`
(oof_pred/y/groups/fam, 4200×26 rows).
Verdict: ranker == teacher (three feature sets, aligned measurement).
Remaining rerank levers: onset/state row features, per-family rankers.

## Rerank variants + path teleport (MEASURED 2026-11-25, Task 5, seed=0)
Variant 1 = post-hoc calibrated rerank on `stage2-oof.npz` (identical
episodes/groups; `rerank_top1`, same argsort tie-breaking as `_report`):
| variant | votable top-1 | pooled top-1 | n | bar ≥0.7 |
|---|---|---|---|---|
| baseline (rerun) | 0.667 | 0.461 | 2712/4200 | FAIL (gap 0.033) |
| V1 calibrated (T=0.168 from `ranker-calibration.json`) | 0.667 | 0.461 | 2712/4200 | STRIKE (Δ 0.000 — T preserves argmax, Guo 2017) |
| V2 truncation_level 5→2 (loss focuses top positions; identical splits via shared `_lambdarank_cv` core) | 0.665 | 0.458 | 2712/4200 | STRIKE (Δ −0.002/−0.003, noise; MRR 0.557 uncompared) |

Max 2 variants reached — bar stays missed, no silent revivals. Ranker
verdict: **STRUCK at 0.667** (abstain-gate ships without it).

Path teleport (64): PPR `flow_teleport` in `src/possibility.py`
(teleport = ranker-softmax × flow mass, α=0.85) wired into the ranked arm
(`--teleport`; flow mass = max over steps of up+down `buffer_*`
occupancy via `_line_edges`). Ranked-arm re-run moved with the 11-25
battery regen (old 0.162/0.413 of 11-11 is stale data, not a code change):
| arm (n=167, seed=0, k=3) | root-hit@1 | subseq@3 | mean-k |
|---|---|---|---|
| ranked re-run | 0.072 | 0.287 | 1.8 |
| ranked + teleport α=0.85 | 0.072 | 0.287 | 1.8 |

Keep rule: ≥ rerun+0.030 with subseq no-regress (absolute 0.192 assumed
the stale 0.162 baseline). Measured Δ +0.000 → **diagnostic-only**.
Mechanism: flow mass is non-degenerate (18/22 machines nonzero per ep)
and teleport flips node-top1 in 28/167 eps (mean |Δp| 0.033) — wash
flips with no truth direction; k-best ordering absorbs the rest.

## Tev decider (MEASURED 2026-11-25, n=60 seed=0)
`scripts/eval_tev.py` (defaults n=60/seed=0, `--transport cli|http`) over the
frozen T=300 battery (`artifacts/m0b_mass_*.parquet`, 48 shards). 60 episodes
sampled seed=0, 53 measurable (7 skipped: clean truth or no onset entries).
Rich per-candidate criteria (onset tick/kind/state + `evidence_for` channel
bits) present. Transport lineage: `tev1:4b` (7954dce22bc6) in this Ollama
build (v0.40.16) is a decision-model runner — `/api/generate` returns HTTP
400 and `/api/chat` reports "does not support chat", so `TevClient`'s HTTP
path cannot reach it; the eval uses an eval-only CLI transport
(`CliDecisionClient` in `scripts/eval_tev.py`: one
`ollama run tev1:4b --ask/--choice` per question, 60 s per-ask cap).
`TevClient`'s 300 s class default is untouched (fix is an explicit eval-side
timeout). Per-call latency ~0.1 s (model GPU-resident).
| metric | value | n |
|---|---|---|
| tev machine top-1 | 0.094 (5/53) | 53 |
| tev family top-1 | 0.132 (7/53) | 53 |
| null/abstain rate | 0.000 | 53 |
| teacher stage-1 ref | 0.671 | 2712 |

Pathology: default-choice bias — machine answer B7S on 49/53, family `loss`
on 51/53. Gated self-consistency (machine-only, 5 votes, same 53 episodes):
0.094 (5/53) — unchanged, still < 0.3.
Verdict: **KILL as decider** (0.094 << 0.671 teacher; SC confirms < 0.3).
Disposition: tev kept for phrasing only; ranker stays decider. Never piped
into ranker.

## Template faithfulness (MEASURED 2026-11-25, n=60 seed=0)
`scripts/eval_jev.py` (defaults n=60/seed=0) over the frozen T=300 battery
(`artifacts/m0b_mass_*.parquet`, 48 shards). Deterministic P/R from
`src/faithfulness.py` (slot recall + trace-coverage recall); NLI arm gated
on `VERDANDI_MNLI_PATH`, skipped honestly without it.
| metric | value | n |
|---|---|---|
| template citation precision | undefined (0 non-abstain cards) | 0/60 |
| template slot recall | undefined (0 non-abstain cards) | 0/60 |
| template trace-coverage recall | undefined (0 non-abstain cards) | 0/60 |
| abstain rate | 1.000 (60/60) | 60 |
| NLI faithfulness | SKIPPED (no local MNLI model) | — |

Lineage: `src/faithfulness.py` (`NliUnavailable`-gated 3-run x 2-order
aggregator, flip-kill 0.20) + `requirements-eval-nli.txt` (eval-only deps;
`requirements.txt` stays CPU-only/no-torch). Fixture recall is 1.0 by
construction (`tests/test_eval_faithfulness.py`, stub clients only).
Verdict: without a Jev decision client every card abstains by design, so
corpus P/R is vacuous — the slot-recall gate is in place as a regression
gate and bites once a decider client exists. NLI numbers explicitly
deferred: no MNLI weights cached (B1), no torch/transformers installed
(B2); download + n=60 NLI run need a quiet machine / lane decision.

## Ranker calibration (MEASURED 2026-11-25, ranker-level T+Platt)
Fit on OOF-val episodes only (fam-stratified 50/50 split, split_seed=0;
n_fit=2100 eps), all numbers below on disjoint EVAL episodes (n=2100) —
never fit on the reporting split. Platt over isotonic (eval-scale n≈2100
episodes is the small-n regime). tau picked on FIT at risk≤0.3, frozen,
applied to EVAL.
| split | T | ECE before→after | NLL before→after | tau | coverage | risk | forced | gated |
|---|---|---|---|---|---|---|---|---|
| ranker EVAL votable (n=1337) | 0.168 | 0.383→0.068 | 2.840→2.031 | 0.187 | 0.893 | 0.284 | 0.662 | 0.716 |
| ranker EVAL pooled (n=2100) | 0.168 | same fit | same fit | 0.187 | 0.578 | 0.294 | 0.455 | 0.706 |

Platt(a=4.355, b=-1.817); margin_def = top1−top2 of T-scaled ranker candidate
softmax probs. Artifact: `artifacts/ranker-calibration.json` (T/a/b/tau +
risk-coverage curve + lineage: battery_seed=0, stacked_seed=0, split_seed=0).
Abstain-gated rerank keeps rank order (no re-ranking by calibrated prob);
gate converts silence+low-conf to abstain at ~0.29 risk on pooled eval.

## Open-set exclude-held-5 (MEASURED 2026-11-25, true unknown-reject)
Held-5 machines: ASM1/ASM2/B7P/B9/C6. Teacher retrained excluding all
held-5-rooted episodes (train_windows_n=80800, HistGBM max_iter=300 seed=0,
same identity features/norm as train_origin) → eval on held-5 only:
| metric | value | n |
|---|---|---|
| exclude-held window forced top-1 | 0.000 | 8582 |
| exclude-held episode pooled top-1 | 0.000 | 760 |
| exclude-held episode votable top-1 | 0.000 | 347 |
| in-fleet teacher window forced top-1 on held-5 (leaky ref) | 0.296 | 8582 |

Zero forced accuracy is the closed-set expectation (unseen labels cannot be
named) — the shippable quantity is abstention, not forced accuracy.
Gate transfer (raw-margin Platt a=5.657/b=-3.603 fit on 38312 non-held fault
windows, tau=0.044 @risk≤0.3 frozen there → held-5 fault windows n=8582):
coverage 0.490, risk 0.413, abstain 0.510.
Transfer verdict: risk 0.413 EXCEEDS the 0.3 budget on truly unseen machines —
the 11-11 T=2.58 row (cov 0.337 @ risk 0.300, different margin_def/battery)
does not reproduce as a risk guarantee here; abstain-by-gate is the measured
unknown-reject behavior (abstain ≈0.51 at this operating point).

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

## Sensor / onset (prior handoff numbers, not re-measured here)
Sensor top-1 0.26–0.33, onset err ~90 ticks. Process top-1 0.76, onset err 2.0.

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
Open-set retrain (exclude-held, 2026-11-25): forced top-1 on truly unseen
machines is 0.000 (closed-set expectation); the measured unknown-reject is
abstention — raw-margin gate abstains 0.510 at risk 0.413 on held-5
(n=8582), over the 0.3 budget. Forced-accuracy transfer is not claimed.
- Per-hop delay calibration: bounds ASSUMED (0,60) pending histogram.
- Cost-weighted metric: deferred per user (accuracy-only bars stand).

## Voided (leak-contaminated, struck from the record)
Identity classifier 0.606, stacked 0.608/0.610, dense retrieval 1.000
(GT-anchored `stale_hold_run`/`reject_flag_count`/`down_run` features).
Clean identity 0.674 stands. Frozen v7 exposure bounded at -3.4pp.
