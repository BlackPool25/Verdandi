# SHIP_STATUS — reviewer-readable ship record (69, signed 2026-11-24)

Branch: `m0b-t-build`. Scope authority: PRISSUE-66 sign-off in
`docs/PROJECT_REPORT.md` §5/§8. Scope list consumed by Tasks 7–10.
Reason codes (verbatim): `ship | abstain_sensor | abstain_weak_family |
abstain_transfer | abstain_low_conf | abstain_rerank | abstain_paths |
abstain_tev`.

Measured-only: every number carries n/seed/lineage or is labeled
unmeasured. Battery lineage unless noted: frozen `m0b_mass` T=300
(4200 fault + 600 clean), MASTER_SEED=777
(`scripts/freeze_m0b_battery.py:22`). Eval scripts default seed=0
(`eval_sensor_stack`, `eval_paths`, `eval_tev`, `eval_jev`).

## 1. Per-component status

| Component | Status | Code | Evidence |
|---|---|---|---|
| Detection (retrained frozen sentinel, thr 0.6 + 2-of-3) | SHIP | `ship` | 0.800 @ clean-fire 0.032, n=4200/600, `DIAGNOSIS_QUALITY.md:10` |
| Detection (tighter thr 0.65) | SHIP (alt point) | `ship` | 0.759 @ 0.017, n=4200/600, `DIAGNOSIS_QUALITY.md:11` |
| Process attribution (stage-2 ranker, votable) | SHIP gated | `ship` / `abstain_rerank` | 0.673 vs bar ≥0.70 (gap 0.027), n=2665, `DIAGNOSIS_QUALITY.md:20` |
| Calibration gate (T=2.58 + Platt) | SHIP mechanism, wiring owed (Task 7) | `abstain_low_conf` | ECE 0.246→0.034, NLL 2.465→1.366, n=96000 (seed unrecorded), `DIAGNOSIS_QUALITY.md:48-53` |
| Transfer / unseen machines (held-5) | SHIP as abstain behavior | `abstain_transfer` | forced 0.327, τ=0.739, coverage 0.337 @ risk 0.300, n=8945 (seed unrecorded), `DIAGNOSIS_QUALITY.md:56-65` |
| Strong families (breakdown/delay/loss) | SHIP gated | `ship` | 0.752/0.753/0.810, `DIAGNOSIS_QUALITY.md:40-43` |
| Weak families (bias/drift/quality/spike) | ABSTAIN | `abstain_weak_family` | 0.226/0.313/0.412/0.247, `DIAGNOSIS_QUALITY.md:40-43` |
| Path layer (ranker evidence) | ABSTAIN, diagnostic-only | `abstain_paths` | 0.162/0.413, n=167 same-seed, `DIAGNOSIS_QUALITY.md:35-38` |
| Tev-as-decider | ABSTAIN, phrasing-only pending n=60 | `abstain_tev` | UNMEASURED (no tev numbers recorded; Task 4) |
| Sensor attribution | ABSTAIN BY DESIGN (65-B) | `abstain_sensor` | 0.033–0.067 vs bar ≥0.4, n=60 each, `SIM_BASELINE.md:107-113` |
| Cost-weighted metric | PERMANENTLY DEFERRED (70) | — | no build; accuracy-only bars stand |

Abstain-gated pooled E2E (DERIVED, unmeasured as E2E): ~0.214 coverage @
~0.70 selective accuracy on unseen-machine-type episodes; forced pooled
(MEASURED) 0.432–0.436. Derivation + caveats in `PROJECT_REPORT.md` §8.

## 2. Struck ledger (bar misses + tripwires)

| Struck item | Bar | Measured | Tripwire / note |
|---|---|---|---|
| Rerank authority (forced top-1 ≥0.7) | votable ≥0.70 | 0.673, n=2665 | gap 0.027 = teacher cap (ranker == teacher 0.671); max 2 variants (Task 5) or struck |
| Path layer as ship | root-hit@1 ≥ +0.03 over 0.162, subseq no-regress | 0.162/0.413, n=167 | teleport lever or struck (Task 5); diagnostic-only meanwhile |
| Tev-as-decider | machine top-1 ≥0.3 (else strike) | UNMEASURED | n=60 pinned-seed run (Task 4); <0.3 → self-consistency re-measure once, then strike to phrasing-only |
| Sensor stack program | top-1 ≥0.4, FA cut ≥30% | 0.033–0.067, n=60 each | missed by ~10×; EBF accumulates nothing — program struck, `abstain_sensor` by design (65-B) |
| Family specialists v1/v2/v3 | +0.10 over 0.226–0.412 @ FAR 0.05 | 0.000–0.062 chance-level | three variants dead; program struck, weak families abstain |
| Hybrid flow ranker rows | flow adds gain | 0.070/0.087 identical both arms | struck; v2 physics converts silence→flow evidence for firing head only |
| v2 general retrieval claim | ON beats OFF @ matched clean-fire, FULL mix | CONFIRMED full-mix: obs+flow ON 0.719 vs obs-only OFF 0.680 @ cf 0.063 vs 0.080, thr 0.7 (same direction @ 0.5; n=700+300/arm, seed-identical) | firing-head claim kept (Task 3); ship/abstain dispositions unchanged |
| τ=0.080 (all-windows) as serving gate | — | coverage 1.000 @ risk 0.300 | gates nothing; serving τ = held-5 0.739 only |
| Closed-set transfer eval | structural transfer | 0.0 | struck; open-set retrain owed (Task 2/75) |
| Same-grid tuning cited as general evidence | — | — | held-out seeds owed before general claims (global tripwire) |
| Any invented number in LLM output | — | — | template-only fallback (global tripwire) |

Older voided (leak-contaminated, struck from record): identity 0.606,
stacked 0.608/0.610, dense retrieval 1.000, clean identity 0.674 stands,
frozen v7 exposure bounded −3.4pp (`PROJECT_REPORT.md` §3).

## 3. Open-issue links (PRISSUE-61..75; text refs — Linear IDs, no URLs invented)

| Issue | Title | State after this task | Owner |
|---|---|---|---|
| PRISSUE-61 | Calibration gate → report pipeline | OPEN — consumes scope codes + ranker numbers | Task 7 |
| PRISSUE-62 | Tev decider @ scale (n=60 vs 0.671) | OPEN (unmeasured) | Task 4 |
| PRISSUE-63 | Rerank +0.027 → 0.7 votable | OPEN | Task 5 |
| PRISSUE-64 | Path layer teleport lever | OPEN | Task 5 |
| PRISSUE-65 | Sensor decision | CLOSED by this doc (option B signed) | — |
| PRISSUE-66 | Ship decision / abstain-gated scope | CLOSED by this doc (scope signed) | — |
| PRISSUE-67 | Operator card UI | OPEN — consumes scope codes | Task 9 |
| PRISSUE-68 | Engineer dossier view | OPEN — consumes scope codes | Task 9 |
| PRISSUE-69 | Consolidate reports | CLOSED by this doc | — |
| PRISSUE-70 | Cost metric | CLOSED by this doc (permanent deferral) | — |
| PRISSUE-71 | LLM phrasing layer | OPEN — consumes template baseline | Task 10 |
| PRISSUE-72 | Faithfulness harness | OPEN (template half exists) | Task 6 |
| PRISSUE-73 | E2E wiring `report_incident` | OPEN — needs 61+67+68 | Task 8 |
| PRISSUE-74 | v2 general-battery confirmation | OPEN (claim scoped meanwhile) | Task 3 |
| PRISSUE-75 | Open-set retrain + ranker calibration | OPEN | Task 2 |

Detail per issue: `SOLVE_GAPS.md` §§61–75 (repo root, untracked).

## 4. Signatures

- 66 scope (ship + codes + E2E): signed 2026-11-24 → `PROJECT_REPORT.md` §8.
- 65-B sensor abstain-by-design: signed 2026-11-24 → `PROJECT_REPORT.md` §5.
- 70 cost permanent deferral: signed 2026-11-24 → `PROJECT_REPORT.md` §5.
- 69 this file: created 2026-11-24.
