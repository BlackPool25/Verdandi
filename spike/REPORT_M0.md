# M0 Echo-Aware Attribution Spike — REAL 20-fault battery path

Harness: `spike/m0_echo.py` (quarantine, never merge). Twin + 20 seeded faults + quantile/IQR + fixed
veto-mask reused verbatim from `spike/battery_rq1_rq2.py`. No new libs (numpy/simpy/psutil only — no
context7 lookups needed, IDs: none). RNG `SeedSequence` throughout; scoring RAW point-wise;
point-adjusted INADMISSIBLE (not used). Raw trace: `spike/trace_m0.jsonl`.

## Echo-suppression rule
Downstream alarm at (t,m) is suppressed (attributed upstream) iff an upstream machine u<m fired in
[t−W−(m−u), t] with `score[u] ≥ score[m,t]`. Score condition encodes echo physics (0.45^lag decay:
echoes are weaker than their source); window encodes propagation lag. Veto-mask (M5 2× margin) kept
unchanged, applied last. **Lag-window choice: W=5 = PCMCI tau_max(2) + LAT_GATE(3) ≥ max line-graph
hops (5).** n floor 800 (KQ1) re-verified: n=800-vs-full flip 0.310 < 0.40 HOLD.

## Ablation OFF vs ON (same process → within-run delta valid; 20 faults)
| | P | R | F1 | AC@1 | AC@1 lat≤3 |
|---|---|---|---|---|---|
| OFF (battery baseline rerun) | 0.560 | 0.934 | 0.700 | 0.80 | — |
| ON (echo rule) | 0.594 | 0.934 | **0.726** | **0.80** (16/20) | 0.80 (16/20) |
| Δ | **+0.034** | +0.000 | **+0.026** | 0 | — |

Per-fault: dP>0 on 14/20, dP<0 on 0/20, dR≠0 on 0/20 — pure precision gain, zero recall cost.
(Note: OFF 0.700 vs battery REPORT 0.734 is cross-run `hash()`-seed jitter inherited verbatim from the
battery twin's `SeedSequence((seed, hash(id)))`; ablation delta within-run is unaffected.)
Variant sweep (principled only): score-conditioned W=8 → F1 0.759; window-without-score W∈{3,5,8} →
F1 ≤0.736 WITH recall loss (0.88/0.85) — rejected. Principled ceiling ≈ 0.76.

## Bars (F1≥0.85 + AC@1≥70% + flip<40% + p99≤30s/fault + total<600s)
F1 0.726 < 0.85 ✗ (misses by 12.4pts; needs P 0.779 at R 0.934) | AC@1 0.80 ✔ | flip tau2 14.4% ✔
(tau3 21.2%, lag-stability 0.889 — graph evidence only, never ships) | on_p99 end-to-end 3.8ms ✔ |
wall 8.4s ✔. Vectors V1–V6 ALL PASS: 50-coros 0.023s ✔ | RSS +0.0%@1k/+0.0%@10k ✔ |
200ms-jitter full probe 10/10 ✔ | malformed 10/10 reject ✔ | 10× saturation 2.9ms/fault flat,
MP never built (ADR-0009), richness shed before quantile+echo ✔ | V6 inverted rule F1 0.726→0.699
(strictly degrades → non-vacuous) ✔.

## Verdict: KILL (echo-attribution hypothesis as specified)
The rule works exactly as designed (directional precision gain, zero recall cost, non-vacuous) but
closes only ~1/5 of the gap: 0.700→0.726 vs 0.85 bar. Residual is structural, not attributional —
3/20 faults undetected at R=0 (F-06/F-12/F-14: detector sensitivity, no alarm to attribute), M5
noisy-channel FPs, echo tails. Project posture stays CONDITIONAL per battery (K1 SURVIVE:
AC@1 0.80/flip 14.4%; K2 FIRES: quantile mandatory). No bar softening without L1 reclassification.
Next cheapest step (not this spike): detector-sensitivity work on missed faults, not more attribution.
Saved-cost note: 8.4s CPU-only run kills the echo hypothesis before any attribution infra is built;
no new deps, no torch/ROCm sink, production untouched, spike quarantined.
