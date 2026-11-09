# Operating points (v7 supplement, MEASURED)

Locked alarming: global 0.8/k=1 (unchanged). Diagnosis-side gates below are
measured, not hand-tuned. Source: OOF on `m0b-mass-supplement-v1`
(47,520 windows, w=128/stride 8, invariant 23 feats).

## Per-rung detection thresholds (max-F1 on rung slice)

| rung | thr | window-F1 | recall | policy |
|---|---|---|---|---|
| caricature (4-7σ) | 0.544 | 0.940 | 0.921 | SHIPS — production operating point |
| incipient (1-3σ) | 0.315 | 0.802 | 0.694 | detection-only + fleet index |

## Abstain gate (risk-coverage curve, `scripts/risk_coverage.py`)

- Full-coverage window risk: 0.025.
- At risk ≤2%: coverage 0.977, tau 0.8 → abstain windows with score in
  [0.1, 0.9]. One-sided equivalent: anchor maxscore < 0.9 abstains
  (`--abstain-hi`, battery default). The 0.9 value is now curve-derived,
  not hand-tuned.

## Per-family recalls (tuned, v7)

breakdown 0.98, delay 0.95, loss 0.92, quality 0.90, bias 0.75, spike 0.65,
drift 0.63. Quality lifted 0.39 → 0.90 via sink_all routing (supplement-only).

## Validity notes

Thresholds tuned on OOF are validation numbers, not test. Cross-battery
transfer (frozen T=300 vs T=1000/DR supplement) re-tunes. Real-slice
recalibration pending (see REAL_SLICE_SPEC.md).
