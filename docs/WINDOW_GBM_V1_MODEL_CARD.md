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

## Localizer verdict (trigger-gated tick onset): KILLED as specified

Backward ROI is fundamentally broken (w128 triggers fire ~120 ticks before
onset; the ROI never contains the fault). Forward search works mechanically
but the signals don't separate: max-projection buries incipient 0.5σ shifts
(noise floor ~2.5), root cycle_lag doesn't mark delay onset. Measured
|est - t0| median: structural baseline ~60 vs localizer 12-15 (loss/breakdown
only) and 144-186 (everything else) — bar was <=4/<=6. Surviving lead:
per-machine (not root) counter columns may restore delay; ROI-gated point
head (learned projection) is the remaining localization path.

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
