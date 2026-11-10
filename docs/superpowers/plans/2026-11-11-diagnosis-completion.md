# Diagnosis Completion Program — Extensive Plan (research-backed, 2026-11-11)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close every NO in the ship table: calibrated abstain gate, per-family specialists for the 4 weak families, sensor attribution stack (DOS → RBC → EBF), ranker-evidence path rerun, held-5 transfer table.

**Architecture:** `src/calibrate.py` (temperature + Platt + coverage gate) → ranker/report wiring → per-family binary experts (own variable masks + EWMA/CUSUM accumulation) under the family head → sensor stack (DOS bank → RBC → EBF) → path eval on ranker scores → held-5 transfer table with unknown-reject.

**Tech Stack:** Python, LightGBM/sklearn, numpy/pandas. No torch, no new deps (scipy already available? verify — else Nelder-Mead by hand).

**Spec:** auditor + TEP lanes (`.omo/ulw-research/2026-11-10-teacher-free-pilot/`), reviewer tripwires, user decisions 2026-11-10 (calibrate first, cost deferred, abstain-gated ship OK), research ledger `.omo/ulw-research/20261111-cal-spec/sources.md` (16 searxng queries, ~90 sources, 2 papers read: Fisch 2208.12084, Cartocci 2212.06688).

## Global Constraints

- TDD: failing test first for every behavior; full suite `PYTHONPATH=. pytest -q -p no:cacheprovider -n auto` stays green.
- Frozen detector + 23-feat quarantine untouched; same-battery comparisons only (frozen T=300, supplement never mixed).
- No `torch` outside `src/roi_head.py`; no banned dict-key literals in new src (twin-gates quarantine).
- OOF-only fitting for every calibrator/selector (never in-sample); GroupKFold by episode everywhere.
- Conventional commits, small diffs; never merge/push main without approval.

## Review Focus

- Calibration fit on OOF/held-out folds, never in-sample; ECE reported with 15-bin top-label ECE + cwECE, not vibes.
- Specialists must use per-family variable masks (no 52-wide rerun); accumulation heads (EWMA/CUSUM) tuned on healthy runs for target FAR.
- Sensor stack must beat sensor top-1 0.26–0.33 with FA-cut ≥30% or be struck.
- Transfer table on held-5 machines (ASM1/ASM2/B7P/B9/C6) with unknown-reject rate — not revalidation accuracy.
- Kill bars are tripwires, not aspirations: miss → strike, record, move on.

---

### Task 1: Calibration module (temperature + Platt + coverage gate)

**Why this shape (research):** Guo et al 2017 — temperature scaling (single param) is the best practical multiclass calibrator and beats complex methods on ECE; Dirichlet (Kull 2019) is natively multiclass but needs 26×27 params — unjustified at n=2665 votable. Platt (2-param sigmoid) is the safe choice for small calibration sets vs isotonic (MetricGate guidance; isotonic overfits small-n). Selectors follow Fisch 2208.12084: coverage tuned by threshold quantile on held-out (Prop 4.8), risk-coverage curve (El-Yaniv & Wiener) as the evaluation; cost-aware deferral deferred per user (cost matrix skipped).

**Files:**
- Create: `src/calibrate.py` — `fit_temperature(logits, y, groups) -> T`, `softmax_top1(logits, T)`, `ece_score(probs, y, n_bins=15)`, `platt_fit(margins, correct)`, `platt_predict`, `coverage_curve(conf, correct)` → risk/coverage points + `pick_threshold(risk_target)`.
- Test: `tests/test_calibrate.py`.

**Interfaces:**
- Consumes: OOF logits/probas (teacher `proba_*` first; ranker OOF later — same signatures).
- Produces: `T: float`, `platt (a, b)`, `threshold τ` + ECE/NLL/risk-coverage numbers for the report.

- [ ] **Step 1: Write the failing tests**

```python
def test_temperature_reduces_nll():
    # synthetic overconfident logits: T-fit must give T>1 and lower NLL vs T=1

def test_ece_known_value():
    # hand-computed 15-bin top-label ECE on a 20-sample fixture (±1e-9)

def test_platt_monotone_and_bounded():
    # fitted sigmoid monotone increasing, outputs in (0,1)

def test_coverage_curve_tradeoff():
    # risk strictly non-increasing as coverage decreases on separable fixture
```

- [ ] **Step 2: Run tests, verify each FAILs** (`pytest tests/test_calibrate.py -q`).
- [ ] **Step 3: Implement** (NLL minimization via 1-D search over T — golden-section, no scipy needed; Platt via Newton/IRLS on 2 params; ECE/cwECE; coverage sweep over unique confidences).
- [ ] **Step 4: Measure on teacher OOF** (`oof_identity.parquet` proba_*): ECE before/after T, NLL, Brier, risk-coverage table (coverage 1.0/0.9/0.8/0.7). Record in `docs/DIAGNOSIS_QUALITY.md`.
- [ ] **Step 5: Commit** (`feat(dx): temperature+Platt calibration with coverage gate`).

**Kill bar:** ECE reduction < 20% relative AND risk-coverage flat (risk@0.8 ≈ risk@1.0) → confidences carry no signal; strike calibration, ship accuracy-only.

### Task 2: Ranker-evidence path rerun (decide path layer)

**Why this shape (research):** CausalRCA/RUN precedent — weighted DAG + PageRank inference is the validated pattern; our `upstream_paths` already is the DAG+discount half. GALR uses Top-k/MRR — our metrics already match the literature.

**Files:**
- Modify: `scripts/eval_paths.py` (accept stage-2 scores as evidence).
- Test: extend `tests/test_routes.py` (ranker-score evidence plumbing — synthetic).

- [ ] RED test → GREEN wiring → re-run `eval_paths` (n=167, same seed) with ranker scores.
- [ ] **Keep iff** root-hit@1/subseq@3 beat heuristic 0.132/0.413; else strike path layer (ranker-only), record, delete nothing.
- [ ] Commit.

### Task 3: Per-family specialists (bias/drift/quality/spike)

**Why this shape (research):** TEP IDV3/IDV9/IDV15 precedent — monolithic classifiers fail incipient faults; VS-MEWMA (Jiang 2012) selects variables then monitors the subset (sensitivity gain by dimension reduction); EWMA beats CUSUM/Shewhart for drift faults; adaptive CUSUM-D for drift detection with ARL-tuned λ/h. FDDBenchmark (AIRI) gives TPR/FPR/ADD reporting discipline — adopt ADD (average detection delay) alongside FDR.

**Files:**
- Create: `src/specialists.py` — `select_mask(family, X_clean, y_weak)` (variance/MI-ranked top-k channels), `ewma_head`, `cusum_head` (k=0.5σ, h from healthy-run ARL target), `family_expert(family)` = mask + accumulation + threshold.
- Test: `tests/test_specialists.py` (mask stability across seeds; head ARL on clean; detection delay on synthetic ramp).

**Interfaces:**
- Consumes: window cache + family head labels; quarantine-safe channels only.
- Produces: per-family score + onset; ensemble rule: family head gates, expert refines.

- [ ] RED → GREEN → measure per-family top-1 vs current (0.23–0.41) + ADD.
- [ ] **Kill bar:** family top-1 gain < +0.10 after ≤2 mask/head variants → strike that family's specialist.
- [ ] Commit per family (small diffs).

### Task 4: Sensor stack (DOS → RBC → EBF)

**Why this shape (research):** DOS (Clark bank — one residual model per sensor, each blind to that sensor; sensor fault = excluded-model wins) gives isolation structure; RBC (Alcala/Qin — reconstruction contributions, guaranteed correct vs smearing; ARdR-CP variant for incipient) gives the attribution score; EBF (Cartocci 2212.06688 — per-variable evidence accumulation counters with up/down thresholds) is the FA-cut lever (paper: highly effective at false-alarm reduction).

**Files:**
- Create: `src/sensor_stack.py` — `dos_bank` (leave-one-machine-out residual models on quarantine-safe features), `rbc_scores` (reconstruction along variable directions), `ebf_filter` (evidence counters + thresholds).
- Test: `tests/test_sensor_stack.py` (isolation on synthetic single-sensor fault; FA-cut on clean).

**Interfaces:**
- Consumes: obs/current window stats (never GT-anchored cols).
- Produces: sensor top-1 + FA rate.

- [ ] RED → GREEN → measure vs 0.26–0.33 / FA-cut ≥30%.
- [ ] **Kill bar:** miss either → strike stack, record.
- [ ] Commit.

### Task 5: Transfer table (held-5) + close-out

**Why this shape (research):** Universal domain adaptation with unknown/novel-fault rejection (target has unseen classes — exactly our held-5 case); reject-unknown rate is the honest metric, not forced accuracy.

**Files:**
- Modify: eval scripts (held-5 split ASM1/ASM2/B7P/B9/C6); report `docs/DIAGNOSIS_QUALITY.md`.

- [ ] Held-5 table: per-machine top-1 + unknown-reject rate + abstain rate.
- [ ] Close-out: final full-suite run, fresh-reviewer pass, ship recommendation (abstain-gated per user decision).
- [ ] Commit docs-only.
