# Window GBM v1 — model card

Binary fault-vs-window classifier (HistGradientBoosting, calibrated) +
per-episode-family max-F1 thresholds.

## v2 (current release): w=128 invariant, multi-origin dense battery

Battery: `m0b-mass-balanced-v1` dense cut (4,200 fault across 7 families x 2
rungs x 26 origins + 600 clean; 1.37M rows). Features: 23 origin-invariant
(max/mean/spread across channels per stat + structural counters), fold-fit
clean normalization.

- Window-F1: **0.854** tuned (0.822 untuned), 3-fold GroupKFold OOF
- Episode-hit: **0.987**, clean episode FP: **0.000**
- Per-family recall: breakdown 0.98, delay 0.94, bias 0.88, quality 0.86,
  spike 0.86, loss 0.86, drift 0.69
- Per-origin recall: **0.75 - 1.00** (worst B1 0.748)
- Runtime: 7.1 ms/window, ~112k windows/s, reload-identical
- Streaming delay: p50 0 ticks, max 288 ticks (one late catch)
- Artifact: 23 feats, `artifacts/window-gbm-w128-v1/`

## v1 (superseded reference): w=32 absolute, A0-only battery

Window-F1 0.963 tuned, episode-hit 1.00 — measured on single-origin data;
does not transfer (multi-origin collapse to 0.75 proved it). Kept as the
dense-1-origin reference only.

## Killed alternatives (do not revive without new evidence)

- Point-wise pool (F1 ceiling 0.645 at 3%; Bayes math in journal).
- State features (cut LOF VUS 0.49 -> 0.40); in-fold synthetic injection (~zero).
- 16-config GBM sweep (flat 0.905-0.918); quality w64 head (F1 0.0).
- Fold-fit unit normalization alone (0.7457, unchanged — scale was not it).
- Origin-invariant w=32 (0.738 — identity was not it either).
- Density alone at w=32 (3x data, 0.724 — coverage was not it).
- Diagnosis that survived: sparse families needed accumulation time (w=128),
  structural families (delay/loss/breakdown) transfer via root counters.

## Limits

- Fixed episode length 300; onset uniform in [120, 300-dur-5].
- No real-plant validation data exists in this repo.
- Bench peak RAM (~16 GB dense / ~5 GB v1) is shard loading, not the model
  (model files total < 5 MB).
