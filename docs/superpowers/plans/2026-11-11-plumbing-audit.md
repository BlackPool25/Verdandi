# Phase 1 Plumbing-Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove, per family×rung, whether each fault's effect reaches a monitored variable — and name the defendants.

**Architecture:** Read-only paired sims (fault-on vs fault-off, fixed seed): inject max-mag fault, measure standardized deviation on contractually designated carriers within the fault window. Failures become named routing/duration fixes (separate tasks, only for failures).

**Tech Stack:** Python, simpy twin (`src/twin.py:1875 run_episode`), sklearn (z-scores only, no models), pytest.

**Spec:** `docs/superpowers/specs/2026-11-10-fix-program-design.md` (Phase 1 + constraints + approach record)

## Global Constraints

- TDD failing-test-first for every behavior change.
- Frozen detector v7 + quarantine (23 invariant feats) untouched.
- Same-battery comparisons only (frozen T=300 manifests; never mix supplement T=1000).
- GT columns eval-only except Head-A train inputs.
- No `torch` outside `src/roi_head.py`.
- No banned dict-key field names in new src code (`family`, `sensor_vs_process`, `hop` — use `fault_family`, `coord_class`/`sensor_verdict`, `hop_est`).
- Conventional commits, small diffs; full suite stays green.
- No sim edit without a failing plumbing test naming it; sim edits confined to routing/duration classes (magnitudes, noise, core dynamics frozen).
- After touching worker plumbing, run slice tests with n-jobs>1.

## Review Focus

- A fault whose carrier fires only after `t1` (window too short, not plumbing) must read as a horizon finding, not a failure — the audit reports firing tick vs window end.
- `run_episode` determinism: same seed + same fault must give bitwise-identical records, else paired comparison is noise — pinned by test.
- Carrier lists that silently exclude the only firing variable (e.g. quality sink counter not in monitor set) must fail loudly, not pass vacuously — the test asserts the monitor set is non-empty per family.
- Stochastic streams (`_spawn_streams` per seed): fault-on/off pairs share the seed, so RNG draws are identical up to the fault — the test asserts this by re-running one pair twice.
- A 7σ fault invisible in obs must fail the audit even if a downstream counter fires late — origin-channel check and carrier check are reported separately.

## File Structure

- `src/plumbing.py` (new): carrier definitions per family + paired-run comparison + audit verdicts. One responsibility: fault-effect reachability, no diagnosis, no ML.
- `scripts/audit_plumbing.py` (new): CLI over the 5×2 matrix, prints the pass/fail table with firing ticks.
- `tests/test_plumbing.py` (new): determinism, monitor-set non-emptiness, origin-vs-carrier split reporting, known-loud control (breakdown must pass).
- Modify: none in Phase 1 (read-only by design). Routing/duration fixes are follow-up tasks owned by audit failures.

## Task 1: Carrier map + paired-run harness

**Files:**
- Create: `src/plumbing.py`
- Create: `tests/test_plumbing.py`

**Interfaces:**
- Consumes: `src.twin.run_episode(seed, fault)` record dict (`states`, obs columns, `flow_stats`); `src.twin.compute_hop` for downstream sets.
- Produces: `CARRIERS: dict[str, list[str]]` (family → monitored columns); `paired_z(fault, seed, carriers, k) -> dict` (per-carrier max standardized deviation + firing tick).

**Steps:**

- [ ] **Step 1: Write the failing test** in `tests/test_plumbing.py`:

```python
def test_breakdown_carrier_fires():
    from src.plumbing import CARRIERS, paired_z
    fault = {"origin": "B2", "class": "breakdown", "t0": 130, "dur": 40}
    out = paired_z(fault, seed=0, carriers=CARVERS["breakdown"], k=3.0)
```

```python
    assert out["fired"] is True and out["tick"] - 130 < 40
```

```python
def test_determinism():
    from src.plumbing import paired_z
    from src.plumbing import CARRIERS
    fault = {"origin": "B2", "class": "breakdown", "t0": 130, "dur": 40}
    assert paired_z(fault, 0, CARRIERS["breakdown"], 3.0) == paired_z(fault, 0, CARRIERS["breakdown"], 3.0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. python3 -m pytest tests/test_plumbing.py -x -q -p no:cacheprovider`
Expected: FAIL with "No module named 'src.plumbing'" / import error

- [ ] **Step 3: Implement `CARRIERS` + `paired_z(fault, seed, carriers, k)` in `src/plumbing.py`**

Carriers per family (monitored columns only, all computable live): breakdown/drift/bias/spike → origin `obs_*` + `current_*`; loss → downstream arrival/buffer/throughput counters + origin obs; quality → test-sink reject counter + origin obs. Paired run: same seed fault-on vs `fault=None`; per carrier, max |z| vs fault-off baseline (frozen mean/std from the off-run prefix); fired = max|z| ≥ k within `[t0, t1]`; tick = first crossing.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. python3 -m pytest tests/test_plumbing.py -q -p no:cacheprovider`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/plumbing.py tests/test_plumbing.py
git commit -m "feat(dx): plumbing carrier map + paired-run harness"
```

## Task 2: Audit CLI + 5×2 matrix

**Files:**
- Create: `scripts/audit_plumbing.py`
- Test: extend `tests/test_plumbing.py` (matrix completeness test)

**Interfaces:**
- Consumes: `src.plumbing.paired_z`, `CARRIERS`; `FAULT_RANGES` max-mag per family (`src/twin.py:440-444`).
- Produces: stdout 5×2 table (family × rung → PASS/FAIL + firing tick + carrier); exit 1 on any FAIL.

**Steps:**

- [ ] **Step 1: Write the failing test**

```python
def test_matrix_covers_five_by_two():
    from scripts.audit_plumbing import MATRIX
    fams = {f for f, _ in MATRIX}
    assert fams == {"loss", "quality", "drift", "bias", "spike"}
    assert {r for _, r in MATRIX} == {"caricature", "incipient"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. python3 -m pytest tests/test_plumbing.py -x -q -p no:cacheprovider`
Expected: FAIL with "No module named 'scripts.audit_plumbing'" (import via `importlib`)

- [ ] **Step 3: Implement `MATRIX` + `main()` in `scripts/audit_plumbing.py`**

Max-mag fault per family×rung (top of `FAULT_RANGES`; representative origin per line: B2 fork, A7 mid-line, C6 deep-line); run `paired_z`; print table; exit 1 on FAIL. Import the script in tests via `importlib.util.spec_from_file_location` (scripts are not a package).

- [ ] **Step 4: Run test + full audit to verify it passes and the table prints**

Run: `PYTHONPATH=. python3 -m pytest tests/test_plumbing.py -q -p no:cacheprovider`
Expected: PASS
Run: `PYTHONPATH=. timeout 600 python3 scripts/audit_plumbing.py`
Expected: 5×2 table with firing ticks

- [ ] **Step 5: Commit**

```bash
git add scripts/audit_plumbing.py tests/test_plumbing.py
git commit -m "feat(dx): plumbing audit CLI + 5x2 matrix"
```

## Task 3: Verdicts → named defendants (no code unless audit fails)

**Files:**
- Modify: `docs/superpowers/specs/2026-11-10-fix-program-design.md` (record results; no code if all pass)

**Interfaces:**
- Consumes: audit table from Task 2.
- Produces: per-FAILURE fix task (routing/duration only), filed as separate plan tasks; per-PASS clean bills.

**Steps:**

- [ ] **Step 1: Run the audit and record the table in the design doc**
- [ ] **Step 2: For each FAIL, open one fix task naming the defendant** (e.g. "loss decrement never reaches downstream arrival counter — wire into part-flow or expose counter"); each fix gets its own failing plumbing test first
- [ ] **Step 3: Commit the verdict record**

```bash
git add docs/superpowers/specs/2026-11-10-fix-program-design.md
git commit -m "docs(dx): plumbing audit verdicts"
```

## Self-Review

1. **Spec coverage:** Phase 1 fully covered (carriers, paired runs, 5×2 matrix, exit = table, eval battery frozen, no-sim-edit rule). Phases 2–4 are separate plans (scope check). k=3σ, frozen Phase-I baseline, fault's own window, FAULT_RANGES source all in tasks.
2. **Step scan:** each test step names exact assertions; code steps give exact signatures (`paired_z(fault, seed, carriers, k)`, `MATRIX`, `main()`); verification steps give commands + expected outputs. `importlib` note covers the scripts-not-a-package trap.
3. **Type consistency:** `paired_z` returns dict with `fired: bool`, `tick: int|None` (+ per-carrier detail); used consistently in Tasks 1–2.
4. **Review Focus:** five lines above, each with its test: horizon-vs-failure (firing tick reported), determinism (test), non-empty monitor set (test to add in Task 1 Step 1 — builder: add `assert CARRIERS[fam]` non-empty per family to the Task 1 test), seed-shared RNG (test), origin-vs-carrier split (reported separately per Task 1 `paired_z` output shape).
5. **Proportion:** plan ≈ spec Phase 1 section; code blocks are tests/signatures only, no bodies transcribed.
