# Verdandi Diagnosis — Project Report (2026-11-10)

## 1. Mission
Factory digital twin (Python/simpy, `src/twin.py`): 26 machines, 7 fault
families, 2 magnitude rungs. Build a diagnosis layer that triggers on
detection and reports WHICH machine, WHAT fault type, onset tick,
severity, and causal trace — top-1 attribution ≥0.5 stepping to 0.85
pooled (later decomposed: retrieval ≥0.75 @ clean-fire ≤0.05 AND
rerank top-1 ≥0.7).

Working tree: `m0b-t-build` branch. TDD, full suite green, conventional
commits. No torch (LightGBM CPU allowed).

## 2. System as built (end-to-end, all wired)
```
detect (frozen v7 GBM, 23 invariant feats, 2-of-3 confirm → anchor)
  → changed set (PELT + state/counter onsets)
  → candidates = BFS radius-2 both dirs (~2-5 machines, fallback full 26)
  → node scores (heuristic direction signature; stage-2 slot ready)
  → ranked upstream PATHS (upstream_paths: sum × coherence, tau gate,
     dilution discounts, normalized probabilities) — not single nodes
  → twin-fork forecast (fault vs clean branch, predicted cascade)
  → incident store link-or-dedupe (sqlite hermetic / postgres live)
  → structured report (ranked paths + per-node table + upstream/downstream)
```

## 3. Attained metrics (MEASURED only; voided numbers struck, not footnoted)
| Layer | Metric | Value | Bar | Verdict |
|---|---|---|---|---|
| Detection (v7 frozen) | window-F1 / hit / clean-FP | 0.89 / 0.92 / 0.01 | — | SHIPS |
| Detection (v7, frozen battery, thr sweep) | retrieval / clean-fire | 0.507–0.568 / 0.000 | — | flat (thresholds don't move it) |
| Detection (retrain on frozen, thr 0.6) | retrieval / clean-fire | **0.800 / 0.032** | ≥0.75 @ ≤0.5 | PASS |
| Rerank (stage-2 LambdaRank, votable) | top-1 / MRR | rerun 0.667 / V2 0.665 max (teacher 0.654, n=2712) | ≥0.7 | STRUCK after 2 variants; gate ships without it |
| Rerank teacher (26-way GBM vote) | top-1 | 0.654 rerun (0.671–0.674 pre-regen) | — | ranker == teacher (capped) |
| E2E pooled | top-1 | 0.432–0.436 | old 0.5 | decomposed bars apply |
| Routes (ranker evidence, re-baselined on regen) | root-hit@1 / subseq@3 / mean-k | 0.072 / 0.287 / 1.1 | — | diagnostic-only stands; teleport Δ+0, flips wash out |
| Family typing | pooled / 3 strong / 4 weak | 0.502 / 0.75+ / 0.23–0.41 | — | split confirmed |
| Sensor attribution | top-1 | 0.26–0.33 | ≥0.4 | FAIL (stack unbuilt) |
| Onset | process med-err / sensor | 2.0 / ~90 | ≤25 | process PASS, sensor FAIL |
| Calibration (teacher OOF windows) | T=2.58, ECE 0.246→0.034, NLL 2.465→1.366 | — | MEASURED (n=96000; seed unrecorded in doc — provenance incomplete) |
| Transfer (held-5 fault windows) | forced 0.327 / τ=0.739 / coverage 0.337 @ risk 0.300 | risk≤0.3 | MEASURED (n=8945; seed unrecorded in doc — provenance incomplete) |
| Cost-weighted metric | — | — | PERMANENTLY DEFERRED, signed §5 (70) |

VOIDED (leak-contaminated, struck): identity classifier 0.606,
stacked 0.608/0.610, dense retrieval 1.000 (root-anchored
stale_hold_run/reject_flag_count/down_run features). Clean identity
0.674 stands. Frozen v7 exposure bounded −3.4pp.
v6 digests: none pinned in this report; per `docs/SIM_SPEC.md` the v3-era
digests are NON_COMPARABLE and no v6 replacement digest is pinned until
PRISSUE-30 re-measures at battery (explicitly unpinned, not missing).

## 4. Root causes established (with evidence)
1. **Retrieval wall = physics + missing features.** f·√W/σ law (Zhao
   Lemma 3); flat threshold sweep; TEP 3/9/15 precedent. NOT a threshold
   problem. Fixed partially by training on deployment battery (+0.26).
2. **Rerank ceiling = teacher.** Three feature sets, identical 0.67 —
   vote fractions can't beat the voter.
3. **Sensor collapse = smearing.** Coupled state offsets; modest-fault
   regime per RBC theory. Attribution-side problem; sim left untouched.
4. **Quiet families = signal physics, not rung.** Loss 75% caricature
   yet 429/600 silent; delay 100% incipient yet fires. Count/level/
   ramp/transient/reject signatures need per-family features.
5. **Estimated onsets ≠ causal order.** Median downstream dt ≈ 0 to
   negative (left-overlap). Delay hard-gates removed; soft coherence kept.

## 5. Decisions on record (user-approved)
- Audit-then-fix; sim authority = routing/duration only (magnitudes,
  noise, dynamics frozen). Plumbing audit: ALL 10 PASS → sim clean bill.
- Decomposed bars replace pooled ≥0.5.
- LambdaRank first; RBC veto; specialized models ok; radius-2 both dirs;
  postgres live + sqlite hermetic; upstream path enumeration with
  dilution; per-episode softmax + Platt calibration (protocol ready).
- Retrain firing model on deployment battery (measured +0.26).
- **[66-SCOPE signed 2026-11-24]:** ship = detect + process attribution +
  calibrated abstain gate; everything else abstains with reason codes
  (`ship | abstain_sensor | abstain_weak_family | abstain_transfer |
  abstain_low_conf | abstain_rerank | abstain_paths | abstain_tev`).
  Scope table + abstain-gated E2E recomputation in §8; consumed by
  Tasks 7–10. Lineage: `docs/DIAGNOSIS_QUALITY.md` + `docs/SIM_BASELINE.md`;
  every number below carries n/seed/lineage or is labeled unmeasured.
- **[65-B signed 2026-11-24]:** sensor attribution ABSTAINS BY DESIGN
  (option B). Evidence: D-PCA(10)+RBC-T2+EBF(paper params) top-1
  bias 0.050 / drift 0.067 / spike 0.033 (n=60 each, script default
  seed=0, lineage `docs/SIM_BASELINE.md:107-113`) vs bar ≥0.4 —
  missed by an order of magnitude; clean-FA ~0 shows EBF works but
  there is nothing to accumulate (contributions never concentrate:
  small amplitudes + no redundancy). Plus auditor dual-obs Goodhart
  warning: optimizing a dual-obs sensor score risks gaming the
  observable, not plant truth. No plant-plausibility case for dual-obs
  was produced, so option A is rejected per protocol E. Sensor stays
  an open problem; UI renders `abstain_sensor`, never a guess.
- **[70-DEFER signed 2026-11-24]:** cost-weighted metric PERMANENTLY
  DEFERRED. Accuracy-only bars stand; no ops costs elicited, no
  cost-weighted threshold/re-rank will be built. Cheapest close in batch.

## 6. Killed without revival rights (measured)
Naive argmax 0.12; coordination-count 0.372; mean-fusion 0.67; gated
combiner 0.63; torch ROI ×2; lag-flow 0.056; CUSUM/EWMA-as-confirm;
naive+Mahalanobis directional gates; strength-weighted 0.0; delay
compensation; score-gated onsets; CROPS leg; oracle GT onsets 0.0;
variation block; closed-set transfer eval (structural 0.0);
per-machine F1 thresholds (0.697 vs 0.715); masked teacher alignment
(0.377); uncalibrated margins; invariant-window features for ranker.
Sensor stack program: D-PCA+RBC-T2+EBF 0.033–0.067 vs 0.4 bar
(`docs/SIM_BASELINE.md:107-113`); sensor attribution ships as
`abstain_sensor` only (65-B, §5).

## 7. Remaining work (in order) — all DONE (Tasks 2–5, 7; see SHIP_STATUS.md close-out)
1. **Rerank**: V1 calibrated 0.667, V2 trunc-2 0.665 → STRUCK (max 2).
2. **Routes with ranker evidence**: re-baselined 0.072/0.287; teleport Δ+0 → diagnostic-only stands.
3. **Sensor stack**: struck (65-B); ships as `abstain_sensor` only.
4. **Calibration fit + gate**: live in `diagnose_incident` (τ=0.739, VERIFY risk 0.044 exclude-held).
5. **Transfer table**: exclude-held retrain recorded (Task 2); held-5 risk 0.413 — transfer cited as abstain behavior, never as guarantee.
6. **Cost metric**: permanently deferred (70).
7. **Per-family CUSUM retrieval**: unchanged (needs calibrated thresholds).

## 8. Ship verdict: SIGNED CONDITIONAL SCOPE (66, 2026-11-24 — supersedes NOT YET)

Ship = detect + process attribution + calibrated abstain gate.
Everything else abstains with a reason code, never a guess.

### Scope table (reason codes consumed by Tasks 7–10)
| Component | Disposition | Code on abstain | Evidence (measured-only) |
|---|---|---|---|
| Detection (retrained frozen sentinel, thr 0.6 + 2-of-3) | SHIP | — | retrieval 0.800 @ clean-fire 0.032, n=4200 fault + 600 clean, battery MASTER_SEED=777 (`scripts/freeze_m0b_battery.py:22`), lineage `docs/DIAGNOSIS_QUALITY.md:10` |
| Process attribution (stage-2 LambdaRank, votable) | SHIP (gated) | `abstain_rerank` (ranker struck: V2 max 0.665 <0.70) | rerun votable 0.667 (teacher 0.654, n=2712); calibration-aware + trunc-2 tried, struck after 2 |
| Calibration gate (T=2.58 + Platt, τ=0.739 held-5) | SHIP (gate live in `diagnose_incident`, VERIFY risk 0.044 exclude-held) | `abstain_low_conf` when conf < τ | ECE 0.246→0.034, NLL 2.465→1.366, n=96000 teacher OOF windows; artifact `artifacts/calibration.json` |
| Strong-family episodes (breakdown/delay/loss) | SHIP (gated) | — | family top-1 0.752/0.753/0.810, lineage `docs/DIAGNOSIS_QUALITY.md:40-43` |
| Weak-family episodes (bias/drift/quality/spike) | ABSTAIN | `abstain_weak_family` | family top-1 0.226/0.313/0.412/0.247, lineage `docs/DIAGNOSIS_QUALITY.md:40-43` |
| Unseen-machine (held-5 type) episodes | ABSTAIN unless conf ≥ τ | `abstain_transfer` | forced 0.327, coverage 0.337 @ risk 0.300, n=8945 windows (seed unrecorded — provenance incomplete), lineage `docs/DIAGNOSIS_QUALITY.md:56-65` |
| Path layer (ranker evidence) | ABSTAIN (diagnostic-only) | `abstain_paths` | re-baselined root-hit@1 0.072 / subseq@3 0.287, n=167 (regen moved it; old 0.162 stale); teleport Δ+0, flips wash out |
| Tev-as-decider | STRUCK as decider (phrasing-only) | `abstain_tev` | machine 0.094 (5/53) / family 0.132, n=60 pinned seed; SC confirms kill; ranker stays decider |
| Sensor attribution | ABSTAIN BY DESIGN (65-B) | `abstain_sensor` | 0.033–0.067 vs bar ≥0.4, n=60 each (script default seed=0), lineage `docs/SIM_BASELINE.md:107-113` |

`ship` marks shipped predictions; all other codes render reason + coverage
in-product (Tasks 7–10) and never a guess.

### Pooled E2E recomputed under abstain-gated scoring (66)
- Forced pooled (MEASURED): top-1 0.432–0.436, lineage
  `docs/DIAGNOSIS_QUALITY.md:27-33` (frozen sentinel + stage-2; decomposed
  bars supersede the old ≥0.5 pooled bar).
- Abstain-gated (DERIVED — arithmetic combination of measured components,
  UNMEASURED as an E2E run): detection silence 1535/4200 = 0.365 already
  abstains (`docs/SIM_BASELINE.md:10-12`); of votable episodes the held-5
  gate predicts on 0.337 @ risk 0.300. Overall coverage ≈
  (2665/4200) × 0.337 ≈ 0.214 of fault episodes predicted; selective
  accuracy ≈ 1 − 0.300 = 0.70. I.e. **~21% coverage @ ~0.70 selective
  accuracy on unseen-machine-type episodes** (DERIVED, unmeasured).
  In-distribution (all-windows τ=0.080): coverage 1.000 @ risk 0.300 —
  gates nothing; serve held-5 τ=0.739 only.
- Caveat (unmeasured mapping): transfer numbers are window-level,
  retrieval/silence are episode-level; the window→episode mapping is
  unvalidated. Tasks 75/11 must confirm with a held-out episode-level run
  before any general claim.

### Signatures
- 66 scope + E2E recomputation: signed 2026-11-24, m0b-t-build.
- 65-B sensor abstain-by-design: signed 2026-11-24 (§5).
- 70 cost-metric permanent deferral: signed 2026-11-24 (§5).
- Consolidated per-component status + struck ledger: `docs/SHIP_STATUS.md` (69).
