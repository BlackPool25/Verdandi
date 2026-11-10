# Sim C-Fixes Implementation Plan (auditor's cut)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert silent loss/quality episodes into observable ones via physical coupling + sink routing, under full protocol hygiene.

**Architecture:** Two sim mechanisms (loss count-coupling, quality sink-routing for all origins), each gated by the existing `paired_z` audit harness, with old-vs-new batteries reported side by side. No gain/volume knobs, no imposed ordering, no new channels.

**Tech Stack:** Python, simpy twin (`src/twin.py`), `src/plumbing.py` audit harness.

**Spec:** auditor report (session, 2026-11-10) + `.omo/ulw-research/2026-11-10-teacher-free-pilot/` lanes. Auditor is binding: C-loss-drain + C-quality-routing are the only approved physics changes; D1/B1/A3/A2/B3 rejected.

## Global Constraints

- TDD: failing test first for every behavior; full suite `PYTHONPATH=. pytest -q -p no:cacheprovider -n auto` stays green.
- Twin-gates stay green: determinism (replay-hash), conservation, quarantine (no banned tokens in src).
- Sim change and diagnosis change never in one commit; same-battery comparisons only.
- Gains/budgets frozen: `FAULT_RANGES`, `±6σ` clamp, 8% rate budget, funnel/pileup gates must keep passing — re-derive, never silently trip.
- `sev`/ladder fields stay ladder-gated (no new leakage surface).
- Conventional commits, small diffs.

## Review Focus

- Silent-rate accounting per (family × rung), old vs new battery — the change must shrink silence, not just move errors.
- Quality routing must not imprint GT-shaped timing (rejects mediated through sink mechanics, observable only).
- Loss coupling must not exceed clamp or break rate budget.
- Battery v2 manifest/coverage/funnel gates green.
- Old hard battery kept and re-reported (no goalpost loss).

---

### Task 1: Baseline lock (protocol E setup)

**Files:**
- Modify: none (measurement only)
- Test: none (record only)

**Interfaces:**
- Consumes: frozen `m0b_mass` battery artifacts.
- Produces: `docs/SIM_BASELINE.md` — silent rate per (family × rung), route root-hit@1/subseq@3, family quality/loss top-1, twin-gate suite result.

- [ ] **Step 1:** Run twin-gates + plumbing audit on current tree, record PASS/FAIL.
- [ ] **Step 2:** Measure silent share by (family × rung) from `artifacts/onsets.parquet` + OOF votable flags.
- [ ] **Step 3:** Commit `docs/SIM_BASELINE.md` (docs-only commit).

### Task 2: Quality sink-routing for all origins

**Files:**
- Modify: `src/twin.py` (`_quality_rate` routing / `quality_sink_all` wiring), battery config flag.
- Test: `tests/test_twin_quality.py` (extend: off-sink origin produces sink rejects).

**Interfaces:**
- Consumes: existing `quality_sink_all` mechanism (`twin.py:1996-2002`), `_quality_rate` (`twin.py:490-503`).
- Produces: flag-wired sink routing, default OFF in frozen battery, ON in v2 battery.

- [ ] **Step 1: Write the failing test** — off-sink quality origin yields sink-side reject/degrade evidence within T=300.
- [ ] **Step 2: Run test, verify FAIL.**
- [ ] **Step 3: Implement** (wire routing, keep gains/ranges frozen, all observables only).
- [ ] **Step 4: Run tests** (new + twin quality/conservation/determinism).
- [ ] **Step 5: Commit** (`fix(twin): quality sink-routing for all origins`).

### Task 3: Loss count-coupling

**Files:**
- Modify: `src/twin.py` (loss sites `979-982` + clones: physical count/timing consequence).
- Test: `tests/test_twin_quality.py` or new `tests/test_twin_loss_coupling.py`.

**Interfaces:**
- Consumes: `paired_z` carriers (`plumbing.py:20-21`) as acceptance.
- Produces: loss moves buffer/flow/count observables; clamp + budget green.

- [ ] **Step 1: Write the failing test** — loss episode moves a count/flow carrier vs fault-off baseline.
- [ ] **Step 2: Run test, verify FAIL.**
- [ ] **Step 3: Implement** (mediated coupling only — drain/blocked-put/cycle consequence, no direct GT-shaped writes).
- [ ] **Step 4: Run tests** (new + gates).
- [ ] **Step 5: Commit** (`fix(twin): physical count coupling for loss`).

### Task 4: Battery v2 + old-vs-new report

**Files:**
- Modify: battery config/manifest for v2; `docs/SIM_BASELINE.md` → add v2 column.
- Test: manifest/coverage/funnel gates.

- [ ] **Step 1:** Generate v2 battery (gains frozen, flags ON).
- [ ] **Step 2:** Re-measure Task 1 metrics on v2; silent Δ + route Δ + gates.
- [ ] **Step 3:** Commit report (docs-only).
