# Window GBM v1 — model card

Binary fault-vs-window classifier (HistGradientBoosting, calibrated) +
per-episode-family max-F1 thresholds.

## v2 (current release): w=128 invariant, multi-origin dense battery

Battery: `m0b-mass-balanced-v1` dense cut, collision-free (4,200 fault across
7 families x 2 rungs x 26 origins + 600 clean; seeds from 40000/45200).
Features: 23 origin-invariant (max/mean/spread across channels per stat +
structural counters), fold-fit clean normalization. 3-fold GroupKFold OOF.

- Window-F1: **0.846** tuned (0.807 untuned @0.5)
- Episode-hit: **0.990** tuned (0.910 untuned), clean-episode alarm rate at
  tuned point: **0.853** — high by design (recall-first point)
- Per-family window recall: breakdown 0.97, delay 0.94, loss 0.88, bias 0.86,
  quality 0.85, spike 0.86, drift 0.86
- Per-family episode hit: 0.93 - 1.00 (loss 0.928 lowest)
- Per-origin window recall: **0.82 - 1.00** (worst C7 0.820)
- Runtime: 6.8 ms/window, ~119k windows/s, reload-identical
- Streaming delay: p50 0 ticks (early-fire on wide windows inflates this)
- Artifact: 23 feats, `artifacts/window-gbm-w128-v2/`
- Wide-battery check (rug=wide: 3x noise floors, drift/gain, 1% dropouts):
  tuned F1 **0.818** (vs 0.846 dense, -0.036), episode-hit 0.986, per-family
  recall all >= 0.87 (drift 0.88, quality 0.91 — *up* vs dense), per-origin
  0.81-1.00. Randomization costs precision, buys recall on weak families.
- Threshold-free triage: **VUS-PR 0.68** (buffer-integrated, per-episode mean)
- NAB event scores (global 0.5 operating point): standard 0.41 / low-FP 0.08 /
  low-FN 0.58 — single-number NAB retired; report the triple
- PA%K window-F1: K=0 (any-overlap) 0.766; K>=0.25 vacuous (=0.0) — at w=128
  even a fully-containing window overlaps ~11% fault, so overlap-fraction
  criteria cannot score this width (width critique on record)
- Optimism gap: tuned 0.846 vs global-0.5 0.807 = 0.039 (threshold shopping price)
- Episode-hit clustered (by-origin) CI: [0.71, 0.81] at the 0.5 point

Operating tradeoff (global threshold, OOF):

| thr | win-P | win-R | win-F1 | epHit | cleanEpFP |
|-----|-------|-------|--------|-------|-----------|
| 0.3 | 0.750 | 0.856 | 0.799  | 0.995 | 0.987     |
| 0.5 | 0.904 | 0.729 | 0.807  | 0.910 | 0.630     |
| 0.6 | 0.951 | 0.695 | 0.803  | 0.831 | 0.325     |
| 0.7 | 0.972 | 0.672 | 0.794  | 0.788 | 0.145     |
| 0.8 | 0.984 | 0.651 | 0.784  | 0.753 | 0.055     |

Dwell (alarm iff k of trailing windows fire) at 0.6: k=2 -> hit 0.77 /
clean 0.16; k=3 -> 0.69 / 0.09. Dwell loses to raising the threshold on every
measured exchange (0.6->0.8 buys -0.27 clean-FP for -0.08 hit; dwell k1->k2
buys -0.16 for -0.06 plus delay). **Locked default: global 0.8, k=1**
(hit 0.75 / clean 0.055) — see `docs/WINDOW_GBM_RUNBOOK.md`. Shipped
per-family tuned thresholds stay behind a high-C_FN flag only.

## v1 (superseded reference): w=32 absolute, A0-only battery

Window-F1 0.963 tuned, episode-hit 1.00 — measured on single-origin data;
does not transfer (multi-origin collapse proved it). Kept as the
dense-1-origin reference only.

## Localizer verdict (trigger-gated tick onset): PARTIAL — ship narrow

Backward ROI dead (triggers fire ~120 ticks early; ROI never contains the
fault). Forward search splits: loss/breakdown counter onsets are precise but
biased (median |est-t0| 13/15, p90 15/15); split-half bias calibration
(stale -13, down -15) brings held-out error to median 2/0, p90 4/0 — inside
the <=4 bar on the confirmation split. SHIPPED for these two families as
counter_onset_fwd + documented per-family bias (the negative sign means the
counter run leads the labeled onset — recorded, not explained).
Killed: delay (root cycle_lag never marks onset, 123) and all obs families
(111-184; max-projection buries 0.5σ shifts under ~2.5 noise floor).
Per-machine (non-root) counters may restore delay — untested lead.
Killed: multiclass specialist head (8-class GBM) — detection F1 0.795 <
binary 0.846; family attribution works only for structural families
(0.74-0.81) and is chance-level for obs families (0.13-0.18 vs 0.125 random),
confirming the invariant representation erases family identity along with
machine identity. Per-family thresholds on the binary head remain the family
mechanism. Killed: hybrid gate confirmer — global F1 0.8463 -> 0.8416,
hit 0.989 -> 0.979, clean-FP unchanged 0.853: gates veto true loss windows
(recall 0.88 -> 0.82) while clean FPs come from families gates cannot see.
The gate is stricter than the model where it applies and blind where it
would matter — wrong combiner, correctly killed.

## Disclosure (read as an ML engineer)

Intended use: triage ranking + per-episode alarming on 128-tick windows from
this twin, at the locked 0.8/k1 point. Out of scope: tick-level onset
(localizer killed), real-plant deployment without the sim2real program,
any operating point other than a cost-elicited one.

Discrimination (tuned OOF, 3-fold GroupKFold, n=96k windows):

| family | n | P | R | F1 | MCC | R 95% CI |
|---|---|---|---|---|---|---|
| breakdown | 12,000 | 0.991 | 0.974 | 0.983 | +0.96 | .970–.978 |
| delay | 12,000 | 0.984 | 0.945 | 0.964 | +0.92 | .939–.950 |
| loss | 12,000 | 0.990 | 0.881 | 0.932 | +0.86 | .873–.888 |
| bias | 12,000 | 0.768 | 0.864 | 0.813 | +0.56 | .855–.872 |
| spike | 12,000 | 0.782 | 0.860 | 0.819 | +0.57 | .851–.868 |
| drift | 12,000 | 0.747 | 0.857 | 0.798 | +0.52 | .848–.865 |
| quality | 12,000 | 0.733 | 0.854 | 0.789 | +0.49 | .845–.862 |

Calibration: ECE 0.017 (10 equal-mass bins) — scores are honest probabilities
on twin data. Threshold-free: VUS-PR 0.68. Optimism gap (global-0.5 vs
per-family tuned): 0.039 — the tuned line is validation-flattered, not test.

Validation grade (Steyerberg terms): internal (GroupKFold) + internal-external
(per-origin spread 0.82–1.00). NO external validation: twin-only, no real
plant slice. Nested-CV honest estimate: not run (threshold optimism is the
only selection bias; model/hyperparameters were fixed, so nested would move
numbers by noise, not signal — recorded, not claimed).
Episode-hit 0.99, clustered-by-origin 95% CI [0.985, 0.993].

Decision: lock 0.8/k1 (deploy PPV ~28% at 3% prevalence vs 4–19% for the
alternatives; cost-dominant for any miss:FP ratio below ~70:1). NAB triple at
global 0.5: standard 0.41 / low-FP 0.08 / low-fn 0.58 — reported, not
optimized; single-number NAB retired as uninterpretable.

## Data incident 2026-11-09 (recorded, resolved)

The first dense battery had a fault/clean episode-ID collision (clean block
landed inside the fault block): ~200 clean episodes silently became faults
and clean-FP 0.000 was vacuous. Fixed with disjoint ID blocks + assertion +
regression test; all v2 numbers above are from the collision-free rebuild
(4,800 unique episodes verified).

## Killed alternatives (do not revive without new evidence)

- Point-wise pool (F1 ceiling 0.645 at 3%; Bayes math in journal).
- State features (cut LOF VUS 0.49 -> 0.40); in-fold synthetic injection (~zero).
- 16-config GBM sweep (flat 0.905-0.918); quality w64 head (F1 0.0).
- Fold-fit unit normalization alone (0.7457, unchanged — scale was not it).
- Origin-invariant w=32 (0.738 — identity was not it either).
- Density alone at w=32 (0.724 — coverage was not it).
- Diagnosis that survived: sparse families needed accumulation time (w=128),
  structural families (delay/loss/breakdown) transfer via root counters.

## Limits

- Fixed episode length 300; onset uniform in [120, 300-dur-5].
- No real-plant validation data exists in this repo.
- Bench peak RAM (~10 GB dense) is shard loading, not the model
  (model files total < 5 MB).
- OOF-picked thresholds are validation-optimistic; untuned lines are citable.
