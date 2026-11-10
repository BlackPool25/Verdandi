# Teacher-Free Ranker Pilot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Train and measure a vote-free LambdaRank (no teacher proba/vote features) to prove the teacher-free path.

**Architecture:** Add `build_rows_free` beside `build_rows` in `scripts/eval_stacked.py` (sentinel agreement + onset 4 + onehot only), evaluate with identical 3-fold StratifiedGroupKFold LambdaRank, compare votable top-1 vs 0.685 baseline on same episodes.

**Tech Stack:** Python, LightGBM lambdarank, pandas/numpy, pytest.

**Spec:** `.omo/ulw-research/20261110-133217/SYNTHESIS.md` (Path F) + `docs/DIAGNOSIS_QUALITY.md` (bars: rerank votable ≥0.7)

## Global Constraints

- TDD: failing test first for every behavior; full suite `PYTHONPATH=. pytest -q -p no:cacheprovider -n auto` stays green.
- Frozen detector v7 + 23-feat quarantine untouched; same-battery comparisons only (frozen T=300, never mix supplement T=1000).
- No `torch` outside `src/roi_head.py`; no banned dict-key literals in new src code (twin-gates quarantine).
- Conventional commits, small diffs; never merge/push main without approval.
- Ponytail: smallest complete change; no new deps.

## Review Focus

- Silent episodes (1535/4200) score all-zero vote-free rows — expect tie, must not crash; reasonable person expects abstain/low-confidence, not a forced wrong top-1.
- Missing-machine onset default collides with earliest-rank — vote-free rows must keep the same default convention as `build_rows` so comparison is fair.
- Serving parity: `train_stage2_final.py`/`eval_e2e.py` call `build_rows` without onsets — pilot must not silently change serving artifact.
- Group ordering for LightGBM `group` param must be episode-sorted, else lambdas misalign.
- `fshare`/`agree` need sentinel `fired`; when `fired=None` they are zeros — pilot must still run (features off, not crash).

---

### Task 1: Vote-free row builder

**Files:**
- Modify: `scripts/eval_stacked.py` (add `build_rows_free`)
- Test: `tests/test_stacked_votefree.py`

**Interfaces:**
- Consumes: `build_rows(oof, machines, fired, onsets)` semantics; `_direction_feats(onsets, ep, machines)` 4-tuple.
- Produces: `build_rows_free(oof, machines, fired=None, onsets=None) -> (X: np.ndarray [n_rows, 2+4+26], y: np.ndarray, groups: np.ndarray, fam: np.ndarray)` — cols `[fshare, agree] + onset4 + onehot26`; no use of `proba_*`/`pred`.

- [ ] **Step 1: Write the failing test**

```python
def test_rows_free_shape_and_no_teacher():
    import inspect
    import scripts.eval_stacked as es
    assert hasattr(es, "build_rows_free")
    src = inspect.getsource(es.build_rows_free)
    assert "proba_" not in src and "pred" not in src
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. python3 -m pytest tests/test_stacked_votefree.py::test_rows_free_shape_and_no_teacher -q -p no:cacheprovider`
Expected: FAIL with "has no attribute 'build_rows_free'"

- [ ] **Step 3: Implement `build_rows_free(oof, machines, fired=None, onsets=None)` in `scripts/eval_stacked.py`**

Reuse `_direction_feats`; per (ep, machine): `[fshare, agree] + onset4 + onehot`; `fshare/agree` from sentinel `fired` aligned to `oof` index exactly as `build_rows` does; zeros when `fired=None`.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. python3 -m pytest tests/test_stacked_votefree.py -q -p no:cacheprovider`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/eval_stacked.py tests/test_stacked_votefree.py
git commit -m "feat(dx): vote-free ranker rows (no teacher features)"
```

### Task 2: Vote-free eval + measurement vs 0.685

**Files:**
- Modify: `scripts/eval_stacked.py` (`main` gains `--free` flag or `main_free()`)
- Test: `tests/test_stacked_votefree.py` (eval smoke on tiny synthetic OOF)

**Interfaces:**
- Consumes: `build_rows_free` from Task 1; same LightGBM params as `main` (`lambdarank, truncation 5, norm, leaves 7, min_data 20, lr 0.05, rounds 200, early_stop 20`); same StratifiedGroupKFold(n_splits=3).
- Produces: console lines `free episode top1=`, `free votable-only top1=` + `artifacts/stage2-rank-free.txt` (do NOT overwrite `stage2-rank.txt`).

- [ ] **Step 1: Write the failing test**

```python
def test_free_eval_runs_on_synthetic():
    from scripts.eval_stacked import main_free
    assert callable(main_free)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. python3 -m pytest tests/test_stacked_votefree.py::test_free_eval_runs_on_synthetic -q -p no:cacheprovider`
Expected: FAIL with "has no attribute 'main_free'"

- [ ] **Step 3: Implement `main_free()` in `scripts/eval_stacked.py`**

Mirror `main()` CV loop but call `build_rows_free`; print `free episode top1` + `free votable-only top1` with identical votable set definition (`pred != "none"`); save ranker to `artifacts/stage2-rank-free.txt`.

- [ ] **Step 4: Run tests**

Run: `PYTHONPATH=. python3 -m pytest tests/test_stacked_votefree.py tests/test_stage2.py -q -p no:cacheprovider`
Expected: PASS

- [ ] **Step 5: Measure**

Run: `PYTHONPATH=. timeout 1200 python3 -c "import scripts.eval_stacked as e; e.main_free()"`
Expected: prints both top-1 lines; record vs 0.685/0.462 baseline in `docs/DIAGNOSIS_QUALITY.md`.

- [ ] **Step 6: Commit**

```bash
git add scripts/eval_stacked.py tests/test_stacked_votefree.py
git commit -m "feat(dx): vote-free LambdaRank eval"
```

### Task 3 (next, not this pilot): PageRank discount + abstain gate

Deferred until Task 2 number lands. Prototype: personalized PageRank on `upstream_paths` DAG with unsupervised teleport (CUSUM mass / Mahalanobis on 23 feats) as additional ranker feature + low-mass abstain; PU-weighting after.
