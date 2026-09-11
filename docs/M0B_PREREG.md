# M0b Battery Pre-registration (FROZEN)

Status: pre-build. M0b battery not yet run. Ensemble-now + shadow-mode locked (MINIPRO-10).
Scope: OmniLearn R1/R2, OQ-1/2/3/6. Twin-scoped claims only. All numbers below are tripwires, not facts.

Grounding: SIM_SPEC.md §§5 (fault injection), 8 (scoring protocol), 10 (kill-wires); SDD.md §§2.2–2.4 (detector set, graph layer, eval harness); ADR-0013 (GDN-light as learned-graph representative).

## 1. Fault list (frozen, 20–32 seeded faults)

Schema per fault: fault id / machine / t0 / duration / magnitude / class.
Count locked at freeze time within 20–32 inclusive. No additions after first run starts.

| fault id | machine | t0 | dur | mag | class |
|---|---|---|---|---|---|
| F-01 | M1 | tbd | tbd | tbd | drift |
| F-02 | M2 | tbd | tbd | tbd | spike |
| F-03 | M3 | tbd | tbd | tbd | stall |
| F-04 | ASM-GW1 | tbd | tbd | tbd | gateway-drop |
| F-05 | M4 | tbd | tbd | tbd | drift |
| F-06 | M5 | tbd | tbd | tbd | spike |
| F-07 | RWK-GW1 | tbd | tbd | tbd | gateway-rework |
| F-08 | M6 | tbd | tbd | tbd | stall |
| F-09 | M1 | tbd | tbd | tbd | spike |
| F-10 | M2 | tbd | tbd | tbd | drift |
| F-11 | ASM-GW2 | tbd | tbd | tbd | gateway-drop |
| F-12 | M3 | tbd | tbd | tbd | stall |
| F-13 | M4 | tbd | tbd | tbd | drift |
| F-14 | RWK-GW2 | tbd | tbd | tbd | gateway-rework |
| F-15 | M5 | tbd | tbd | tbd | spike |
| F-16 | M6 | tbd | tbd | tbd | drift |
| F-17 | M1 | tbd | tbd | tbd | stall |
| F-18 | M2 | tbd | tbd | tbd | spike |
| F-19 | ASM-GW1 | tbd | tbd | tbd | gateway-drop |
| F-20 | M3 | tbd | tbd | tbd | drift |
| F-21 | M4 | tbd | tbd | tbd | spike |
| F-22 | RWK-GW1 | tbd | tbd | tbd | gateway-rework |
| F-23 | M5 | tbd | tbd | tbd | stall |
| F-24 | M6 | tbd | tbd | tbd | drift |

Gateway quota: ≥20% of faults at assembly/rework gateways (here 7/24 ≈ 29%). Seeded RNG recorded at run time; seed hashes logged before first run. t0/dur/mag frozen per fault before run.

## 2. Calibration (fixed percentile, frozen)

Fixed-percentile threshold on validation-normal segment only, set once, never re-tuned per detector or per fault. Percentile value frozen at run config (e.g. p99, recorded in run log). No per-arm re-calibration.

## 3. Scoring protocol

Primary metric: raw point-wise F1 ONLY, PA-off. No point-adjustment in the primary arm (SIM_SPEC §8).
Control arm: PA-on scored alongside, used only for the protocol-neutrality check: PA-on must flip the detector ranking OR compress the top-gap by ≥0.30, else protocol-neutrality fails and results are not reported as PA-robust.
Close-out bars (unsoftened): F1 ≥ 0.85; AC@1 ≥ 70%; flip < 40%; 95% grounding HELD, misses confined to the escape-taxonomy note (§6).

## 4. Baselines (frozen set)

Quantile baseline + ≥1 GNN (GDN-light per ADR-0013) + MP-discord guardrail. No detector swaps mid-battery. Precedent on record: GDN reports 0.81 on SWaT (external reference point, not a twin prediction; twin-scoped evaluation only).

## 5. Kill-wires (tripwires, not facts)

- Any GNN raw-F1 ≥ 0.60 → drop the learned-graph-deprioritized reading; re-rank with learned-graph-first hypothesis.
- Quantile raw-F1 < 0.60 → re-open detector selection; current set insufficient for this twin.
- All bars in §3 hold as stated or the battery does not close out.

## 6. Escape taxonomy (95% grounding note)

Residual misses must map to: DELAY (late flag, root correct) / LOSS (masked segment, see TC-003/004 extensions) / GATEWAY (assembly/rework propagation ambiguity) / NOVEL (unseeded signature). Unmapped misses break the 95% grounding hold.

## 7. Scoring-code hash (placeholder)

`scoring_commit: <tbd — fill full SHA at run time; battery invalid without it>`

## 8. No-subsetting rule

No dropping faults, detectors, or seeds to clear a bar. Any exclusion invalidates the battery; re-run full or report as failed.
