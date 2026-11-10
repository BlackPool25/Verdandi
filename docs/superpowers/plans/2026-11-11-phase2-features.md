# Phase 2 Per-Family Features + Teacher-Aligned Rerank Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Lift retrieval from 0.54 toward ≥0.75 and rerank from 0.52 toward ≥0.7 on confirmed episodes, per family, with GroupKFold-honest deltas.

**Architecture:** A shared streaming CUSUM-bank module feeds per-family detectors; buffer/flow/sink columns join the identity window feature set (frozen v7 23-feat path untouched); stage-2 ranker rows are rebuilt on v7-fired windows (teacher alignment); per-episode calibration fits T + Platt on held-out episodes.

**Tech Stack:** Python, sklearn HistGBM/LightGBM ranker, simpy twin (read-only sim use), pytest, GroupKFold/StratifiedGroupKFold.

**Spec:** `docs/superpowers/specs/2026-11-10-fix-program-design.md` (Phase 2 + constraints + approach record)

## Global Constraints

- TDD failing-test-first for every behavior change.
- Frozen detector v7 + quarantine (23 invariant feats) untouched — new features go to identity/Head-A paths only.
- Same-battery comparisons only (frozen T=300 battery; never mix supplement T=1000).
- GT columns eval-only except Head-A train inputs.
- No `torch` outside `src/roi_head.py`.
- No banned dict-key field names in new src code (`family`, `sensor_vs_process`, `hop` — use `fault_family`, `coord_class`/`sensor_verdict`, `hop_est`).
- Conventional commits, small diffs; full suite stays green.
- After touching worker plumbing, run slice tests with n-jobs>1.
- No sim edits in this plan (sim got a clean bill in Phase 1).

## Review Focus

- CUSUM baseline frozen at train time; a detector that recomputes μ₀/r on live data reintroduces the Stable-Shift failure (level shifts become invisible) — Task 1 tests that baselines survive a second `fit` call unchanged unless explicitly refit.
- Bernoulli CUSUM reference rate r must come from clean episodes only; fitting r on mixed data silently raises the bar past quiet families — Task 1 tests r against a known p₀ fixture.
- Spike fast path must never route through the CUSUM accumulator (reset absorbs transients) — Task 2 tests a lone 3σ single-tick spike fires while CUSUM stays silent.
- Buffer/flow window features must be causal (trailing windows only); a centered rolling stat leaks the future into the window — Task 3 tests feature equality under future-masking.
- Teacher-aligned stage-2 rows built on v7-fired windows need nested OOF discipline (v7 OOF folds ≠ ranker folds) or the rerank number is leakage — Task 4 tests fold-disjointness explicitly.

---

## Task 1: Streaming CUSUM-bank module

**Files:**
- Create: `src/cusum_bank.py`
- Test: `tests/test_cusum_bank.py`

**Interfaces:**
- Consumes: nothing (pure streaming primitives).
- Produces: `TabularCUSUM(k, h, mu0, sigma0, adaptive)` with `step(x)->bool fire, reset()` — adaptive mode tracks local variance via EWMA (Ahmadini 2025, decided); `BernoulliCUSUM(r, h)` with `step(x01)->bool`; `EWMA(lam, mu0, L)` with `step(x)->(z, breach)`; `SlopePersist(w, k)` with `step(x)->bool`; quality `DynamicSFA` challenger head (Sci China 2026 recipe) evaluated alongside Bernoulli, winner on OOF. All causal, all frozen-baseline.

**Steps:**

- [ ] **Step 1: Write the failing test**

```python
def test_tabular_cusum_fires_on_1sigma_shift():
    from src.cusum_bank import TabularCUSUM
    import numpy as np
    rng = np.random.default_rng(0)
    c = TabularCUSUM(k=0.5, h=5.0, mu0=0.0, sigma0=1.0)
    fired = [c.step(v) for v in rng.normal(0, 1, 20)] + [c.step(v) for v in rng.normal(1.0, 1, 60)]
    assert any(fired[20:]) and not any(fired[:20])
```

```python
def test_baseline_frozen_across_second_fit():
    from src.cusum_bank import TabularCUSUM
    c = TabularCUSUM(k=0.5, h=5.0, mu0=0.0, sigma0=1.0)
    c.fit([10.0] * 50)
    assert (c.mu0, c.sigma0) == (0.0, 1.0)
```

```python
def test_bernoulli_cusum_reference_from_clean_only():
    from src.cusum_bank import BernoulliCUSUM
    import numpy as np
    rng = np.random.default_rng(1)
    clean = (rng.random(2000) < 0.005).astype(int)
    c = BernoulliCUSUM.fit_rate(clean, h=3.0)
    assert 0.003 < c.r < 0.010
```

```python
def test_spike_absorbed_by_cusum_but_caught_by_fast_path():
    from src.cusum_bank import TabularCUSUM, SpikePath
    import numpy as np
    c = TabularCUSUM(k=0.5, h=5.0, mu0=0.0, sigma0=1.0)
    s = SpikePath(w=4, thr=3.0)
    xs = np.zeros(50); xs[25] = 3.5
    assert not any(c.step(v) for v in xs)
    assert any(s.step(v) for v in xs)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. python3 -m pytest tests/test_cusum_bank.py -x -q -p no:cacheprovider`
Expected: FAIL with "No module named 'src.cusum_bank'"

- [ ] **Step 3: Implement `TabularCUSUM`, `BernoulliCUSUM`, `EWMA`, `SlopePersist`, `SpikePath` in `src/cusum_bank.py`**

Pure streaming classes; `BernoulliCUSUM.fit_rate` classmethod estimates r from clean event stream. SpikePath: short-window max + first-difference vs frozen scale, no accumulator.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. python3 -m pytest tests/test_cusum_bank.py -q -p no:cacheprovider`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/cusum_bank.py tests/test_cusum_bank.py
git commit -m "feat(dx): streaming CUSUM bank + spike fast path"
```

## Task 2: Per-family retrieval eval (CUSUM bank on battery streams)

**Files:**
- Create: `scripts/eval_cusum_retrieval.py`
- Test: extend `tests/test_cusum_bank.py` with a battery-shape fixture test (synthetic episode with planted ramp/bias/spike/count-deficit; assert each family's head fires and others stay quiet-ish)

**Interfaces:**
- Consumes: `src/cusum_bank.*`, parquet step rows (obs/current/buffer/flow/test-sink streams per episode).
- Produces: per-family retrieval + clean-fire + median firing delay, printed MEASURED table; gates Phase 3.

**Steps:**

- [ ] **Step 1: Write the failing test** (fixture: synthetic loss stream with p 0.005→0.02 at tick 100; Bernoulli head must fire within 400 ticks; tabular head on flat stream must not)

- [ ] **Step 2: Run test to verify it fails** (no eval script / heads miswired)

- [ ] **Step 3: Implement `scripts/eval_cusum_retrieval.py`** (per-episode streaming over frozen-battery step rows; family heads: loss→Bernoulli on completion events, quality→Bernoulli on test-sink pass/fail, drift→EWMA+slope, bias→tabular, spike→SpikePath; report retrieval/clean-fire/delay per family)

- [ ] **Step 4: Run test + script to verify** (script runs ≤25 min; table printed)

- [ ] **Step 5: Commit**

```bash
git add scripts/eval_cusum_retrieval.py tests/test_cusum_bank.py
git commit -m "feat(dx): per-family CUSUM retrieval eval"
```

## Task 3: Buffer/flow/sink window features (identity path only)

**Files:**
- Modify: `src/window_dataset.py` (identity branch: append trailing stats of buffer/flow/sink columns; frozen invariant branch byte-identical)
- Modify: `tests/test_window_dataset.py` (identity width + causality tests)
- Modify: `scripts/train_origin.py`, `scripts/train_windows.py`, `scripts/finalize_window_model.py` (n_obs paths — identity only)

**Interfaces:**
- Consumes: `src/window_dataset.build_windows` identity path.
- Produces: wider identity rows; `struct_cols_for(invariant=...)` extended with `flow_cols_for`.

**Steps:**

- [ ] **Step 1: Write the failing tests** (identity width grows by 2×n_flow_cols; future-masking test: recompute features with future ticks zeroed, assert identical; invariant width still 23)

- [ ] **Step 2: Run tests to verify they fail**

- [ ] **Step 3: Implement trailing-only buffer/flow/sink stats in `_window_features`** (mean/max over trailing window; never centered)

- [ ] **Step 4: Run tests + quarantine test to verify** (`test_finalize_model` 23-feat pin must stay green)

- [ ] **Step 5: Commit**

## Task 4: Teacher-aligned stage-2 (v7-fired rows)

**Files:**
- Modify: `scripts/eval_stacked.py` (row builder takes v7-fired mask; nested OOF: ranker folds ≠ v7 OOF folds — assert fold-disjointness in-script)
- Test: `tests/test_ranker.py` (fold-disjointness unit test on synthetic groups)

**Interfaces:**
- Consumes: `/tmp/v7_oof.parquet` (frozen, cached), `/tmp/oof_clean.parquet` (identity posteriors), `src/ranker.py`.
- Produces: rerank top-1 on v7-confirmed episodes; expected ≥0.65 (closes the 0.524 teacher-mismatch gap).

**Steps:**

- [ ] **Step 1: Write the failing tests** (fold-disjointness: shared episode across v7-fold and ranker-fold raises; row builder drops non-fired windows)

- [ ] **Step 2: Run tests to verify they fail**

- [ ] **Step 3: Implement mask + nested-CV in `scripts/eval_stacked.py`**

- [ ] **Step 4: Run tests + eval to verify** (rerank on confirmed ≥0.6 else the mismatch hypothesis is wrong — report, don't tune past it)

- [ ] **Step 5: Commit**

## Task 5: Per-episode calibration fit (T + Platt)

**Files:**
- Create: `src/calibrate.py` (fit_temperature, fit_platt_on_margin, selective risk-coverage table)
- Test: `tests/test_calibrate.py` (synthetic: uncalibrated margins show episode-length skew; calibrated remove it — the wave-2a assert)

**Interfaces:**
- Consumes: stage-2 OOF scores + correctness labels per episode.
- Produces: T, Platt (a,b), θ from cost model; risk-coverage + ECE with/without.

**Steps:**

- [ ] **Step 1–5:** standard TDD (failing test → run → implement → run → commit `feat(dx): per-episode calibration`)

## Self-Review

1. **Spec coverage:** Phase 2 fully tasked (CUSUM bank → retrieval eval → window features → teacher-aligned rerank → calibration). Sensor (Phase 3) and transfer (Phase 4) are separate plans, noted not built here. 2026 deltas folded: adaptive-k is a Task-1 follow-up if fixed-k stalls (Ahmadini), SFA challenger for quality is an eval-candidate in Task 2 (Sci China 2026), not a default.
2. **Step scan:** each step names one artifact; test steps carry assertions with spec values (k=0.5/H=5, (H,r) start, w=4/thr=3, frozen baselines).
3. **Type consistency:** `paired_z`-style dicts not reused here; new names (`TabularCUSUM.step(x)->bool`, `BernoulliCUSUM.fit_rate`, `SlopePersist`, `SpikePath`) consistent across tasks.
4. **Review Focus:** five lines, each with its owning test in Task 1–4 steps (frozen baseline, clean-only r, spike isolation, causal features, nested folds).
5. **Proportion:** plan ≈ spec Phase 2; no bodies transcribed except the four one-line recursions the spec fixes.
