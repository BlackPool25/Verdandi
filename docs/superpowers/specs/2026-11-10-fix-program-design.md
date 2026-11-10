# Root-cause fix program: diagnosis accuracy (lanes S/F folded; builder-checked)

## Intent
Pooled top-1 is 0.284 because retrieval caps at 0.54: quiet families
(loss/quality/drift/bias/spike) never fire the sentinel. Fix the actual
causes — sim plumbing where the fault effect never reaches a monitored
variable, per-family features where the signal exists but max-dev windows
can't see it — not thresholds (proven flat 0.507–0.568).

## Decisions (user, 2026-11-10)
- Strategy: audit-then-fix. Falsifiable plumbing tests first; fix only
  proven bugs; per-family features for the rest.
- Sim authority: routing/duration allowed (capped counts, routed sinks,
  longer durations for slow families). Magnitudes, noise, core dynamics
  frozen. No rescaling difficulty.
- Bars (decomposed, replace pooled ≥0.5): retrieval ≥0.75 at clean-fire
  ≤0.05 AND rerank top-1 ≥0.7 on retrieved. Pooled reported, not gated.
- Order: plumbing → per-family features → sensor stack → calibration +
  transfer.

## Approaches considered
1. **Audit-then-fix (picked).** Plumbing tests name defendants
   (loss-count reachability, quality sink routing per origin); only
   failures get sim edits; everything else is diagnosis-side features.
   Trades: slower start, every sim edit evidence-backed.
2. **Sim-first (rejected).** Would fix routing on suspicion; risks
   gaming the benchmark (making faults louder vs making them visible).
3. **Diagnosis-only (rejected).** Cannot recover signal destroyed in
   sim plumbing (e.g. rejects to unmonitored sink); features can't see
   what never arrives.
4. **Policy route (rejected).** Restating the bar without fixes concedes
   loss-caricature silence (429/600 at 4–7σ), which is a bug signature,
   not policy.

## Program
### Phase 1 — plumbing audit (sim, read-only first)
Rule (VLSI transfer): a fault counts as detected only if activated,
propagated, AND reaching an observe point. Per family×rung (loss,
quality, drift, bias, spike × caricature/incipient = 5×2 matrix) on the
frozen battery:
- Inject max-mag fault (top of `FAULT_RANGES` per family,
  `src/twin.py:444+`); fault window = its own `[t0,t1]`.
- Assert some monitored variable deviates > 3σ vs frozen Phase-I
  baseline (≥20–30 clean points) within the duration.
- Carriers (contractual): loss → downstream arrival deficit / buffer
  slope / cumulative expected-minus-actual; quality → sink reject
  counter + reject-rate CUSUM (per-origin where possible); drift/bias/
  spike → origin obs channel.
- N budgets: loss ~300–600 ticks cumulative (3–5% deficit rate math);
  quality = transit(origin→test-sink) + ~100–300 ticks accumulation.
  Drift has no fixed N — CUSUM/long-horizon monitor or explicit
  exclusion with justification (standard TEP practice for 3/9/15).
Failures → routing/duration fixes under sim authority (e.g. wire loss
decrement into part-flow or expose the counter; route per-origin
rejects to the monitored sink — sink_all precedent 0.39→0.90).
Passes → family goes to Phase 2 with a clean bill.
Exit: 5×2 table (pass/fail + named defendant or clean bill).
Eval battery: frozen primary for Phases 1–3; supplement report-only;
Phase 4 owns cross-battery.

### Phase 2 — per-family features (diagnosis, no sim changes)
- loss: Bernoulli/Poisson CUSUM on completion stream
  `B=max(0,B+x−r)`; start (H,r)=(3.0,0.0105) scaled to plant p₀
  (Sandia MRL tables), tune per-family on frozen-battery OOF.
- drift: OLS slope over trailing 64–128 (fit horizon) + EWMA(λ=0.2);
  alarm on slope persistence over 15–45-tick causal decision windows
  (sweep both horizons); CUSUM-D flavor if ramps dominate.
- bias: two-sided tabular CUSUM (k=0.5σ, H=5σ) vs frozen Phase-I;
  shift-start readout free.
- spike: SEPARATE fast path — short-window max (w 4–8) + first
  difference vs frozen-scale threshold (tune; CWT-matched wavelet if
  FPs rise); never through CUSUM (reset absorbs spikes).
- quality: Bernoulli CUSUM on test-sink binary stream + equipment-
  stream FDC fusion; per-operation rates, never plant-wide max.
Shared CUSUM-bank code (loss/drift/bias: same recursion, different
k/H/λ/stream/horizon); spike path and quality sink-tap separate.
Tuning procedure: start from cited tables, tune per family on
frozen-battery GroupKFold OOF; GroupKFold-honest deltas required.
Exit: per-family deltas vs v7 baseline (retrieval + rerank split).

### Phase 3 — sensor stack (attribution-side only; sim coupling untouched)
Per-channel DOS observer bank → RBC (`RBC_i=(ξiᵀMx)²/(ξiᵀMξi)` on
sensor-level PCA per `docs/DIAGNOSIS_FLOW.md` RBC section) → EBF
temporal filter over contributions → optional T-PLS output-relevant
projection for coupled machines. Bars: sensor P@1 ≥0.50 (vs
0.26–0.33); EBF ≥30% false-alarm cut at fixed detection (Cartocci
precedent); T-PLS ≥10pp over RBC-alone (else smearing dominates and
banks are the only lever). Publish min-detectable magnitude per
sensor (Wang limits: no arbitrary-ramp claims). Exit: sensor P@1 +
false-alarm-cut bars met.

### Phase 4 — calibration + transfer
Per-episode softmax + fitted T → Platt on m/std → θ from cost model
(wave-2a protocol: `.omo/ulw-research/20261109-232330/wave-2a-calibration.md`).
Id-backoff prototypes (line/modality/global) + shallow OTDA/JDOT per
held machine, frozen encoder (deep joint retrain destroys features —
TEP-measured). Per-held-machine table ASM1/ASM2/B7P/B9/C6 (novel
benchmark; no leave-one-asset baseline exists). Exit: held-5 table +
transfer gap reported.

## Constraints (standing)
TDD failing-test-first; frozen detector v7 + quarantine (23 invariant
feats); same-battery comparisons; GT columns eval-only (Head-A train
excepted); no torch outside roi_head; no banned dict keys in new src;
conventional commits; full suite green. New: no sim edit without a
failing plumbing test naming it; every sim edit confined to
routing/duration classes.

## Open (research lanes S/F landed 2026-11-10 — folded below)

### Sim-plumbing precedents (lane S — verdict: audit first, numbers pending)
No direct "sink_all" analog with published deltas retrieved; the
DQMNet lead (quality-related incipient faults) and Bernoulli-CUSUM
design tables are the closest load-bearing items. The audit stands on
its own logic (fault effect must reach a monitored variable); external
numbers calibrate horizons, not the decision to audit.

### Per-family recipes (lane F — all MEASURED unless noted)
Shared pattern: accumulate or fit slope over a FROZEN baseline; separate
fast path for transients. Non-negotiable: never recompute μ₀ on live
data (Stable-Shift failure: moving limits obscure level shifts).
- loss: Bernoulli/Poisson CUSUM on completion stream
  `B=max(0,B+x−r)`; MRL 881 parts at 2× defect rate, 231 at 4×
  (Sandia tables, (H,r)=(3.0,0.0105)). Hundreds-of-parts horizon —
  structurally invisible in 128-tick max windows.
- drift: OLS slope over trailing 64–128 + EWMA(λ=0.2); ARL 44→10 at
  1σ vs Shewhart (~4× faster); CUSUM-D/adaptive for ramps;
  EWMA default when drift rate unknown (Hawkins-Wu).
- bias: two-sided tabular CUSUM k=0.5σ/H=5σ vs frozen Phase-I
  (≥20–30 pts); shift-start readout free. TEP: CUSUM found 3 faults
  unobservable by prior methods (with delay).
- spike: SEPARATE fast path — short-window max (w 4–8) + first
  difference; never through CUSUM (reset absorbs spikes). MSDG/Cardiff:
  small windows = transients, broad = trends; one window can't do both.
- quality: Bernoulli CUSUM on test-sink binary stream (same Sandia
  tables); fuse with equipment-stream FDC; per-operation rates, never
  plant-wide max.
Shared bank (loss/drift/bias: same recursion, different k/H/λ/stream);
spike path separate; quality sink-tap separate.
