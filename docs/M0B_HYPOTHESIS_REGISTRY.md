# M0b Hypothesis Registry — battery m0b-train-frozen182 (2026-11-08, updated post-fix)

Manifest sha `57b933a4` (182 fault + 10 clean, seeds 30001+/30201+). Gateway waiver 19.23% logged.
Tiered F1 rule (owner 2026-11-08): ≥0.85 pass; 0.60–0.84 fail + falsification review; <0.60 escalate §5 to P0.
**Tiered bars apply to the TRAINED pool. Baseline rows are the floor, not verdicts.**

## Trained-pool adjudication (OOF decisions, full-episode rows, deployment prevalence)

Trained fused operating point: point-F1 **0.711** (OOF-tuned; optimism caveat ~0.05–0.15 applies,
honest estimate ≈0.58–0.66 — Task 20 nested run pending; was 0.657 pre-normalization).
Clean-row fused rate 0.9% (window-only veto; was 1.5% with whole-episode veto).
Naive OR with quantile (hard union in runner): F1 **0.098** — textbook OR inflation, measured;
the fused operating point, not the OR, is the trained system under test.

| wire | metric (battery m0b-train-frozen182) | status |
|---|---|---|
| H1 N-vs-S | S-arm VUS < best-N VUS by 0.158; F1 reading also negative (S 0.597 max vs LOF 0.669) | Falsified |
| H2 gate +3pp | structural − quantile episode-hit = +0.104 (valid per-episode data; earlier 0.0 was a void join) | Survived |
| H3 per-class +2pp | per-class F1 0.711 vs single global (+0.066) | Survived |
| H4 M-vs-G ±2pp | walk/pcmci absent | BLOCKED (out of scope, not adjudicated) |
| H5 firing | quality-expert clean fires 0/400 kits (≤3/1000 bar met); ≥2-of-3 stability needs repeats | Ambiguous (allowed) |
| USAD/GDN | torch absent in CPU-only env | BLOCKED, never Falsified |

Per-family fused fault-row recall: bias 0.91 / breakdown 0.93 / spike 0.94 / drift 0.66 / loss 0.56 / quality 0.49 / delay 0.44.
Structural gates per-episode hit: breakdown 1.00 / spike-bias 0.58 / delay 0.27 / drift-loss-quality 0.15.
Combined episode-hit (any expert): 0.95 (3 misses, all quality).

## Baseline reference (untrained quantile + gates + CUSUM, battery m0b-baseline-frozen182)

F1 raw 0.080 → 0.098 after RUN-only delay gating + loss-combo + variance gate + ML-OR wiring;
AC@1 0.511; hit 131/182 → 179/182; clean_fp 5837 → 2626 cells.
Delay-gate RUN-only gating removed the STARVED-machine flood (B7S/RWK0 saturate tputlag all episode).
Loss-combo gate (tputlag≥5 AND stale≥1) covers the between-bars signature. Variance gate (ratio≥4)
fires 0/78000 clean cells (free insurance for the blowup direction; our 3 quality misses are
variance-COLLAPSE, not blowup — needs per-episode normalization, Task 19).
