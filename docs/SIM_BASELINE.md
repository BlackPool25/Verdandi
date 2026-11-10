# Sim baseline lock (pre C-fixes, 2026-11-10)

Battery: frozen `m0b_mass` T=300 (4200 fault + 600 clean).
Code: HEAD at plan start (`git log --oneline -1` at commit time).

## Gates (MEASURED 2026-11-10)
- `test_twin_gates` + `test_plumbing` + `test_twin_quality`: 21 passed.
- Full suite: 717 passed, 1 skipped (2026-11-10).

## Silence (MEASURED)
- Battery level (stage-2 eval): votable 2665/4200 → silent 1535/4200 = 0.365.
- Cache level (`window_cache/meta`, 572 fault eps, votable = teacher pred non-none):

| family | silent/total | share |
|---|---|---|
| loss | 65/93 | 0.70 |
| quality | 49/87 | 0.56 |
| bias | 27/78 | 0.35 |
| drift | 31/88 | 0.35 |
| spike | 25/69 | 0.36 |
| breakdown | 0/69 | 0.00 |
| delay | 0/88 | 0.00 |

Confirms audit: silence concentrated in loss + quality-off-sink + incipient sensor rungs.

## Diagnosis numbers on this battery (MEASURED, unchanged by sim work)
- Retrieval 0.800 @ 0.032; rerank 0.685 votable; paths root@1 0.132 / subseq@3 0.413 (k 1.5);
  family 0.502; sensor 0.26–0.33; onset proc 2.0 / sensor ~90; e2e pooled 0.432–0.436.

## v2 firing comparison (MEASURED 2026-11-10, focused quality+loss battery)

## Task 4 hybrid ranker (MEASURED 2026-11-10, focused ON arm — STRUCK)

Teacher OOF retrained on the focused ON cache (`artifacts/focused_on_oof.parquet`,
6000 windows); onsets + flowmap built from the same arm; `fired=None` both
sides (isolates flow value).

| rows | pooled | votable | n |
|---|---|---|---|
| teacher-rows | 0.070 | 0.087 | 200 / 103 |
| hybrid (+2 flow cols, 57.8% nonzero) | 0.070 | 0.087 | 200 / 103 |

Flow features add exactly zero (identical to 3 decimals on live nonzero
inputs) — LambdaRank assigns them no gain given votes+onset. Kill bar
tripped → **hybrid struck**. Caveats: 300-episode OOF is data-starved
(27 classes); quality+loss are the hardest families; `fired=None` removes
sentinel agreement from both sides. Standing conclusion: v2 physics converts
silence→flow evidence for the *firing* head (+0.185 retrieval), but the
*attribution* head cannot use it in row form — per-family specialists or the
path layer are the remaining routes, both unbuilt.

Arms: `artifacts/v2_focus/{off,on}` (200 fault + 100 clean each, seed-identical
grid; ON = sink_all_quality + couple_loss). Caches: `artifacts/cache_v2_{off,on}`
(n=6000 windows each). Head: `eval_fire_flow` GroupKFold HistGBM(max_iter=100).

| arm | tag | thr | retrieval | clean-fire | med-err | n |
|---|---|---|---|---|---|---|
| OFF | obs-only | 0.5 | 0.710 | 0.290 | 8.0 | 200/100 |
| OFF | obs-only | 0.7 | 0.630 | 0.150 | 0.0 | 200/100 |
| OFF | obs+flow | 0.5 | 0.710 | 0.290 | 8.0 | 200/100 |
| OFF | obs+flow | 0.7 | 0.630 | 0.130 | 0.0 | 200/100 |
| ON | obs-only | 0.5 | 0.825 | 0.100 | 0.0 | 200/100 |
| ON | obs-only | 0.7 | 0.815 | 0.030 | 0.0 | 200/100 |
| ON | obs+flow | 0.5 | 0.840 | 0.100 | 0.0 | 200/100 |
| ON | obs+flow | 0.7 | 0.815 | 0.040 | 0.0 | 200/100 |

Gate (Task 3): obs+flow ON vs obs-only OFF — **PASS** (+0.185 retrieval at
thr 0.7 with clean-fire 0.040 vs 0.150). Note the lift is NOT flow-feature
magic alone: ON obs-only also jumps (0.630→0.815) because condemn/reject
routing changes downstream starvation → state → obs texture (mediated,
physical). Caveats: focused battery (quality+loss only — the targeted
families, not a general retrieval claim); clean n=100 (±~4pp noise).

| check | old (frozen) | v2 | Δ |
|---|---|---|---|
| quality eps with sink rejects (n=50 mixed rungs, flag ablation) | 1/50 | 22/50 | +42pp evidence |
| loss caricature sink-reject eps (n=40, drop 0.3) | 0/40* | 21/40 | +52pp evidence |
| loss incipient sink-reject eps (n=40, drop 0.05) | 0/40* | 1/40 | +2pp evidence |
| twin gates (quality/gates/battery/flow/duty/plumbing/conservation + new) | 21 passed | 84 passed | green |
| clean-episode sink rejects (n=8 seeds) | 0 | 0 | no clean-fire regression |

\* old-physics arm not re-run for loss (mechanism absent pre-fix by construction);
quality old arm re-ran (1/50). Scoping (reviewer C1 — read before citing):
new evidence is FLOW/EVENT-level (REJECT_ROUTE, flow counters, parts flags)
— NOT sentinel obs firing, and NO measured diagnosis consumer reads it
(detector allowlists exclude reject/scrap counts; ranker rows are
vote/sentinel/onset only). Detector silence conversion = 0. The sole live
retrieval path is the `eval_fire_flow` obs+flow arm (`F_flow` aggregates
sunk/scrapped/throughput; `scrapped_total` is not quarantined) — unrun on
v2 physics. Claiming silence reduction requires that run (Task 3 wiring),
not these event counts.
- silent Δ, route Δ, gates, family loss/quality Δ.

## Task 3 specialists (MEASURED 2026-11-11 — STRUCK all 4)
- Variant 1 (max-|z| over mask): recall 0.047–0.062 @ FAR 0.05 = chance.
- Variant 2 (CUSUM over trajectories, h tuned clean): recall 0.000–0.013 @ FAR 0.001–0.006 — worse; window-scale trajectories carry no sustained shift.
- Kill bar (+0.10 over 0.226–0.412) missed by ~0.2+ everywhere → family specialists STRUCK (both variants spent).

## Task 3 specialists v3 (MEASURED 2026-11-11 — STRUCK)
Dynamic-lag trajectories (d=10) + CUSUM, same 5% FAR protocol:
bias 0.045 / drift 0.045 / quality 0.012 / spike 0.052 — all chance.
Three variants dead (static max, static CUSUM, dynamic CUSUM).
Program struck: window-cache obs trajectories carry no per-family signal
separable from clean at 5% FAR. Remaining routes: D-PCA sensor stack
(Task 4), family abstain fallback (process-only ship).
