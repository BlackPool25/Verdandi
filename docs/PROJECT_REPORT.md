# Verdandi Diagnosis — Project Report (2026-11-10)

## 1. Mission
Factory digital twin (Python/simpy, `src/twin.py`): 26 machines, 7 fault
families, 2 magnitude rungs. Build a diagnosis layer that triggers on
detection and reports WHICH machine, WHAT fault type, onset tick,
severity, and causal trace — top-1 attribution ≥0.5 stepping to 0.85
pooled (later decomposed: retrieval ≥0.75 @ clean-fire ≤0.05 AND
rerank top-1 ≥0.7).

Working tree: `m0b-t-build` branch. TDD, full suite green, conventional
commits. No torch (LightGBM CPU allowed).

## 2. System as built (end-to-end, all wired)
```
detect (frozen v7 GBM, 23 invariant feats, 2-of-3 confirm → anchor)
  → changed set (PELT + state/counter onsets)
  → candidates = BFS radius-2 both dirs (~2-5 machines, fallback full 26)
  → node scores (heuristic direction signature; stage-2 slot ready)
  → ranked upstream PATHS (upstream_paths: sum × coherence, tau gate,
     dilution discounts, normalized probabilities) — not single nodes
  → twin-fork forecast (fault vs clean branch, predicted cascade)
  → incident store link-or-dedupe (sqlite hermetic / postgres live)
  → structured report (ranked paths + per-node table + upstream/downstream)
```

## 3. Attained metrics (MEASURED only; voided numbers struck, not footnoted)
| Layer | Metric | Value | Bar | Verdict |
|---|---|---|---|---|
| Detection (v7 frozen) | window-F1 / hit / clean-FP | 0.89 / 0.92 / 0.01 | — | SHIPS |
| Detection (v7, frozen battery, thr sweep) | retrieval / clean-fire | 0.507–0.568 / 0.000 | — | flat (thresholds don't move it) |
| Detection (retrain on frozen, thr 0.6) | retrieval / clean-fire | **0.800 / 0.032** | ≥0.75 @ ≤0.5 | PASS |
| Rerank (stage-2 LambdaRank, votable) | top-1 / MRR | 0.673 / 0.56 | ≥0.7 | FAIL (−0.027) |
| Rerank teacher (26-way GBM vote) | top-1 | 0.671–0.674 | — | ranker == teacher (capped) |
| E2E pooled | top-1 | 0.432–0.436 | old 0.5 | decomposed bars apply |
| Routes (heuristic evidence) | root-hit@1 / subseq@3 / mean-k | 0.126 / 0.413 / 1.1 | — | diagnostic; rerun w/ ranker pending |
| Family typing | pooled / 3 strong / 4 weak | 0.502 / 0.75+ / 0.23–0.41 | — | split confirmed |
| Sensor attribution | top-1 | 0.26–0.33 | ≥0.4 | FAIL (stack unbuilt) |
| Onset | process med-err / sensor | 2.0 / ~90 | ≤25 | process PASS, sensor FAIL |
| Calibration / transfer / cost | — | unbuilt | — | missing |

VOIDED (leak-contaminated, struck): identity classifier 0.606,
stacked 0.608/0.610, dense retrieval 1.000 (root-anchored
stale_hold_run/reject_flag_count/down_run features). Clean identity
0.674 stands. Frozen v7 exposure bounded −3.4pp.

## 4. Root causes established (with evidence)
1. **Retrieval wall = physics + missing features.** f·√W/σ law (Zhao
   Lemma 3); flat threshold sweep; TEP 3/9/15 precedent. NOT a threshold
   problem. Fixed partially by training on deployment battery (+0.26).
2. **Rerank ceiling = teacher.** Three feature sets, identical 0.67 —
   vote fractions can't beat the voter.
3. **Sensor collapse = smearing.** Coupled state offsets; modest-fault
   regime per RBC theory. Attribution-side problem; sim left untouched.
4. **Quiet families = signal physics, not rung.** Loss 75% caricature
   yet 429/600 silent; delay 100% incipient yet fires. Count/level/
   ramp/transient/reject signatures need per-family features.
5. **Estimated onsets ≠ causal order.** Median downstream dt ≈ 0 to
   negative (left-overlap). Delay hard-gates removed; soft coherence kept.

## 5. Decisions on record (user-approved)
- Audit-then-fix; sim authority = routing/duration only (magnitudes,
  noise, dynamics frozen). Plumbing audit: ALL 10 PASS → sim clean bill.
- Decomposed bars replace pooled ≥0.5.
- LambdaRank first; RBC veto; specialized models ok; radius-2 both dirs;
  postgres live + sqlite hermetic; upstream path enumeration with
  dilution; per-episode softmax + Platt calibration (protocol ready).
- Retrain firing model on deployment battery (measured +0.26).

## 6. Killed without revival rights (measured)
Naive argmax 0.12; coordination-count 0.372; mean-fusion 0.67; gated
combiner 0.63; torch ROI ×2; lag-flow 0.056; CUSUM/EWMA-as-confirm;
naive+Mahalanobis directional gates; strength-weighted 0.0; delay
compensation; score-gated onsets; CROPS leg; oracle GT onsets 0.0;
variation block; closed-set transfer eval (structural 0.0);
per-machine F1 thresholds (0.697 vs 0.715); masked teacher alignment
(0.377); uncalibrated margins; invariant-window features for ranker.

## 7. Remaining work (in order)
1. **Rerank +0.027**: onset/state/buffer row features in stage-2
   (columns exist in `meta` + `flow_features`; never combined).
2. **Routes with ranker evidence**: re-run path eval on stage-2 scores;
   decide path layer vs ranker-only.
3. **Sensor stack**: DOS bank → RBC → EBF (bars: P@1 ≥0.5, FA cut ≥30%).
4. **Calibration fit**: per-episode softmax + T + Platt; risk-coverage gate.
5. **Transfer table**: id-backoff + shallow OT; held-5 ASM1/ASM2/B7P/B9/C6.
6. **Cost metric**: elicit ops costs; re-rank under expected cost.
7. **Per-family CUSUM retrieval**: heads built + tested; battery eval
   pending clean-threshold tuning (raw-stream version killed on
   clean-fire 1.0 — needs calibrated thresholds, not defaults).

## 8. Ship verdict: NOT YET
Machinery complete and honest; one bar cleared (retrieval), rerank one
step short, sensor + calibration + transfer + cost still open. The gap
is five named items with tests — not fog.
