# M0b Quantile Baseline Audit (detector half of OQ-2 + Phase-1 re-baseline)

Run: `python3 scripts/run_m0b_baseline.py` on frozen manifest `57b933a4…` (182 fault + 10 clean episodes, cal seed 7).
Artifact: `artifacts/m0b_baseline.json` (regenerable, gitignored).

## Headline (raw point-wise F1, PA-off; AC@1 via attribute_top1)

| Metric | Value | Bar | Verdict |
|---|---|---|---|
| F1 raw | 0.159 | ≥ 0.85 | MISS (this is the M0b gap, quantified) |
| AC@1 | 0.423 | ≥ 70% | MISS |
| Fault episodes flagged | 83/182 | — | — |
| Mean latency (hits) | 1.39 steps | ≤ 3 | pass on hits |
| Clean-episode alarm steps | 556/1800 (31%) | — | precision collapse |

## Misses by effect mode (the diagnosis)

| Class | Miss | AC@1 | Reading |
|---|---|---|---|
| spike | 0/26 | 0.92 | covered |
| bias | 0/26 | 1.00 | covered |
| drift | 3/26 (all incipient) | 0.85 | covered; incipient rung is sub-threshold by design |
| delay | 23/26 | 0.08 | NOT covered — moves buffers/inter-arrival, not obs amplitude |
| loss | 25/26 | 0.04 | NOT covered — masked segment, no obs exceedance |
| breakdown | 26/26 | 0.00 | NOT covered — forced DOWN has no obs exceedance signature |
| quality | 22/26 | 0.08 | NOT covered — reject/degrade flags, not obs exceedance |

## Interpretation

The F1 gap is **detector coverage by effect mode, not attribution**. Signal faults (spike/bias/drift) are caught with AC@1 0.85–1.00. Structural faults (delay/loss/breakdown/quality: 92/104 missed) never move obs amplitude past a quantile fence — they move *states, buffers, throughput*. Clean-episode alarms coincide heavily with plant-state dynamics (e.g. 53/180 steps have a machine DOWN from natural breakdowns; wear-drift ramp): the obs-only detector fires on legitimate plant behavior.

## Prescribed fix (feeds PRISSUE-10 Phase-1 + M0b battery H-wires)

Per-class structural gates, not a louder quantile:
- DELAY/LOSS → buffer-occupancy / inter-arrival gates (already schema v6 `buffer_occ`, `tputlag_*`)
- breakdown → DOWN-run gate (`downrun_*`, `is_down`)
- quality → reject/degrade flags (`reject_flag_count`, `degrade_flag_count`, `scrap_flag`)
- Keep quantile/IQR as the signal-class leg + MP-discord guardrail. Gate promotion on per-class recall, never global F1 alone.

Flip% (OQ-2 second half), BARO null (OQ-3), and grounding (OQ-4) remain blocked on walk.py + pcmci_job.py.

## Addendum: trainability probe (the scoreboard that matters)

`scripts/probe_trainability.py` — per-family train-AUC upper bounds (in-sample, signal-existence only) on 2 clean + 7 fault episodes, structural v6 features vs obs-only:

| Family | Struct AUC | Obs-only AUC | Reading |
|---|---|---|---|
| drift | 0.740 | 0.975 | obs wins (signal fault) |
| bias | 0.840 | 1.000 | obs wins |
| delay | 0.780 | 0.252 | structural only (obs worse than chance) |
| loss | 0.742 | 0.282 | structural only |
| breakdown | 1.000 | 0.999 | both (DOWN shifts obs −3σ; quantile is one-sided UP so it missed — add a lower fence) |
| quality | 0.952 | 0.669 | structural wins |
| spike | 0.794 | 1.000 | obs wins |

Every family is learnable from v6 features (worst 0.74, most ≥0.78). The rule-based F1=0.08 measures hand-tuned operating points, not data quality. Recommendation: ML battery next (per-family experts on v6 features, PRISSUE-19); rules become fallback + training-signal generators, not the product.
