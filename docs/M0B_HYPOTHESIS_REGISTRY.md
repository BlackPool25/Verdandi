# M0b Hypothesis Registry — battery m0b-baseline-frozen182 (2026-11-08)

Manifest sha `57b933a4` (182 fault + 10 clean, seeds 30001+/30201+). Gateway waiver 19.23% logged.
Tiered F1 rule (owner 2026-11-08): ≥0.85 pass; 0.60–0.84 fail + falsification review; <0.60 escalate §5 to P0.
**Scope: tiered bars apply to the TRAINED-pool evaluation. The untrained baseline below is the floor
to beat, not a wire verdict.**

| wire | bars (Linear PRISSUE-19) | battery result | status |
|---|---|---|---|
| H1 N-vs-S + unknown-family hedge | +3pp / 0.30 wire | PENDING (no trained pool). Baseline ref: quantile hits 100% spike/drift/bias/breakdown, 27–42% delay/loss/quality | PENDING |
| H2 gate +3pp | +3pp | PENDING | PENDING |
| H3 C/F/P + per-class | +2pp co-default wires | PENDING | PENDING |
| H4 M-vs-G backbones | ±2pp signed | PENDING (walk/pcmci absent — causal half out of scope) | PENDING |
| H5 firing test | 2pp / 3-per-1000 / ≥2-of-3 stability | PENDING. Baseline ref: CUSUM clean-hit 0/10; quality expert adds recall at zero clean cost in this harness | PENDING |

Baseline snapshot (untrained quantile + structural + locked CUSUM): F1 raw 0.080, AC@1 0.511,
hit 131/182, clean_fp 5837 cells, VUS-PR 0.09–0.38/family. Miss escape taxonomy: ALL 51 misses in
delay(15)/loss(19)/quality(17); zero misses in spike/drift/bias/breakdown.
