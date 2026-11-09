# Real-slice calibration spec (parallel track to twin levers)

Purpose: the only measurement that transfers. Twin-only bars overestimate
transfer by 15–35 pts (CWRU/TEP precedent). A small real slice calibrates
thresholds, audits texture realism, and anchors the sim-to-real gap claim.
It is NOT training mass.

## What to collect

- 20–50 fault episodes (any family) + 1–2 weeks of clean operation.
- Same channels as the twin export: obs_<machine> x26, state_<machine> x26,
  tputlag/downrun/dwell per machine, gap buffers, part flags
  (DEGRADE/REJECT), AGV waits.
- 1 Hz sampling aligned to twin tick semantics (1 tick = 1 step).

## Labels (required per episode, else the slice is unusable)

- `family`, `rung` (or magnitude estimate), `onset_tick` (±tolerance noted),
  `root_id`, `gap_to_next_fault` if compound.
- Transient library: settling / queue-drain / load-shift / sensor-artifact
  windows labeled as such (hard negatives for the FP gate).

## Acceptance gates

- G1 texture audit: real STARVED share, AR(1), sine amplitude within 2× of
  twin values, else retune twin before any other lever.
- G2 calibration: sim-only vs sim+real-calibrated model on held-out real
  events; pass if FAR halves at fixed recall.
- G3 no-training-leak: real slice NEVER trains the twin-side heads; it tunes
  thresholds and validates transfer only.

## Sequencing

Start spec/conversations now; twin levers proceed in parallel. If G1 shows
true texture >> sim (3×+), freeze other lever claims until the twin is
retuned — sim deltas would overstate.
