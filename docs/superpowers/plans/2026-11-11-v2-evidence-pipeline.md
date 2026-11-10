# V2 Evidence-to-Pipeline Plan (fire_flow old-vs-new + hybrid ranker)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove or kill the v2 physics at the diagnosis level: old-vs-new firing comparison on a focused battery, then hybrid ranker rows iff flow evidence discriminates.

**Architecture:** Focused quality+loss battery pair (OFF vs ON flags, separate dir — frozen `m0b_mass_*` never touched) → parameterized cache per arm → `eval_fire_flow` both arms → per-machine buffer/flow features into ranker rows → measure vs 0.685 votable.

**Tech Stack:** Python, simpy twin, LightGBM, pandas/numpy.

**Spec:** auditor report + reviewer C1 (evidence must reach a measured consumer) + `docs/SIM_BASELINE.md` v2 column.

## Global Constraints

- TDD: failing test first for every behavior; full suite stays green.
- Frozen artifacts (`artifacts/m0b_mass_*.parquet`, `artifacts/window_cache/`) NEVER overwritten — v2 lives in `artifacts/v2_focus/` + `artifacts/cache_v2_{off,on}/`.
- Same-battery comparisons only: OFF vs ON arms differ ONLY in the two v2 flags (same seeds, same grid).
- No torch; quarantine intact (flow features via `F_flow` aggregates only — `scrapped_total` not quarantined; `reject_flag_count`/part flags stay out).
- Conventional commits, small diffs.

## Review Focus

- OFF/ON arms must be seed-identical grids (same ep ids, same faults minus flags) or the Δ is uninterpretable.
- Cache glob override must default to frozen paths (serving parity: existing cache untouched).
- Ranker flow features must be per-(episode, machine) (buffer_<M> trailing stats); episode-global counters cannot rank within-episode.
- Forced top-1 on silent stays reported as triple metric (pooled / votable / detector-fired), not pooled alone.
- Battery sim cost: keep focused (quality+loss × 2 rungs × 50/cell + 100 clean ≈ 300 eps/arm).

---

### Task 1: Parameterize cache + fire_flow paths

**Files:**
- Modify: `scripts/cache_windows.py` (`--glob`, `--out`), `scripts/eval_fire_flow.py` (`--cache`).
- Test: `tests/test_cache_paths.py` (defaults reproduce frozen constants).

**Interfaces:**
- Consumes: nothing new.
- Produces: `cache_windows.main(glob, out)`, `eval_fire_flow.main(cache)` importable with defaults `artifacts/m0b_mass_*.parquet` / `artifacts/window_cache`.

- [ ] **Step 1: Write the failing test**

```python
def test_cache_defaults_frozen():
    import scripts.cache_windows as cw, scripts.eval_fire_flow as ef
    assert cw.CACHE_DIR == "artifacts/window_cache"
    assert ef.CACHE == "artifacts/window_cache"
    assert hasattr(cw, "main") and hasattr(ef, "main")
```

(tighten: test that `main` accepts overrides — write the signature test first, watch it fail.)

- [ ] **Step 2: Run test, verify FAIL.**
- [ ] **Step 3: Implement** (additive kwargs/flags only; default behavior bit-identical).
- [ ] **Step 4: Run tests** (new + rerun `eval_fire_flow` on frozen cache → numbers reproduce 0.80-ish retrieval line).
- [ ] **Step 5: Commit** (`refactor(dx): parameterize cache/fire_flow paths`).

### Task 2: Focused battery pair (OFF vs ON)

**Files:**
- Modify: `scripts/gen_mass_battery.py` (family filter flag, e.g. `--families quality,loss`).
- Test: `tests/test_battery_v2.py` (filter keeps grid shape per family).

**Interfaces:**
- Consumes: Task 1 paths.
- Produces: `artifacts/v2_focus/off/` + `artifacts/v2_focus/on/` parquet shards, seed-identical.

- [ ] **Step 1: Write the failing test** (filter flag; OFF/ON spec equality except flags).
- [ ] **Step 2: Run, verify FAIL.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Generate both arms** (n_per_cell=50, n_clean=100, seed fixed) + validate gates on the pair.
- [ ] **Step 5: Commit** (code) + report arm checksums (docs).

### Task 3: Old-vs-new firing comparison (THE decisive test)

**Files:**
- Modify: none (measurement only; uses Task 1 entry points).
- Test: none (numbers recorded).

**Interfaces:**
- Consumes: Task 2 arms + Task 1 cache entry points.
- Produces: `docs/SIM_BASELINE.md` v2-firing table: obs-only vs obs+flow × OFF vs ON (retrieval / clean-fire / med-err).

- [ ] **Step 1:** Build `cache_v2_off` + `cache_v2_on`.
- [ ] **Step 2:** Run `eval_fire_flow` both arms; record all six lines.
- [ ] **Step 3:** PASS iff obs+flow ON beats obs-only OFF on retrieval at same clean-fire (else kill v2-diagnosis value; physics stays, pipeline claim struck).
- [ ] **Step 4:** Commit report (docs-only).

### Task 4: Hybrid ranker rows (gated on Task 3 PASS)

**Files:**
- Modify: `scripts/eval_stacked.py` (`build_rows` + per-machine flow cols), test file.
- Test: behavioral (flow-col permutation moves rows; frozen-default rows unchanged).

**Interfaces:**
- Consumes: Task 3 caches (per-(ep,machine) buffer/flow aggregates via `_flow_block` columns).
- Produces: hybrid votable top-1 vs 0.685; no-onehot ablation retained.

- [ ] Steps per TDD (test → fail → implement → pass → measure → commit).
- [ ] Kill bar: hybrid votable < 0.70 after ≤2 feature variants → strike hybrid, keep teacher ranker.

### Task 5: Close-out report

- [ ] Update `docs/DIAGNOSIS_QUALITY.md` + `docs/SIM_BASELINE.md` with the decision (ship hybrid / kill v2-pipeline-value).
- [ ] Commit docs-only.
