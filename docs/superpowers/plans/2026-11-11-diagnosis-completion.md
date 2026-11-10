# Diagnosis Completion Program v2 (paper-grounded, 2026-11-11)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close every NO in the ship table with methods the literature says work for our exact failure modes.

**Architecture:** D-PCA lag augmentation → per-family heads (specialists v3) + sensor stack (RBC-T²/PDC-Q → EBF) → ranker-evidence paths (KEPT) → held-5 transfer → close-out. Calibration DONE (T=2.58, ECE −86%, gate live).

**Tech Stack:** Python, numpy/pandas/sklearn, LightGBM. No torch, no new deps.

**Spec:** `.omo/ulw-research/20261111-cal-spec/paper-synthesis.md` (6 papers read as converted MD) + auditor/reviewer tripwires. User decisions: calibrate-first done, cost deferred, abstain-gated ship OK.

## Global Constraints

- TDD: failing test first; full suite green after every task.
- Frozen detector + 23-feat quarantine untouched (D-PCA lags are derived from the same channels, not new sensors); same-battery comparisons only.
- No banned dict-key literals in new src; OOF-only fitting; GroupKFold by episode.
- Conventional commits; no push/merge without approval.

## Review Focus

- Small-amplitude faults are abstain-by-design (papers: unreliable for ALL methods) — never tune thresholds to force them.
- RBC needs a per-family PDC-Q challenger (CSTR: RBC smears on bias/drift).
- DOS bank dropped (needs analytic observers; data-driven shadow = weaker RBC).
- Kill bars are tripwires: miss → strike, record, move on.

---

### Task 1: DONE — Calibration (T=2.58, NLL 2.465→1.366, ECE −86%, risk 0.30→0.186@0.7)

### Task 2: DONE — Path layer KEPT (ranker 0.162 vs heuristic 0.132; serving parity pinned)

### Task 3: Specialists v3 on dynamic features (bias/drift/quality/spike)

**Why:** TEP review — every incipient success (SSAE 95–99%, LSTM-SAE 93%, dynamic augmentation) uses temporal features; our v1/v2 used static window stats and died at chance.

- [ ] RED: test lag-augmentation shape/determinism + CUSUM-on-lagged-traj recall on synthetic ramp (reuse `tests/test_specialists.py`).
- [ ] GREEN: `src/specialists.py` += `lagged_stats(X, d=10)` (per-channel lag means/max over window sequence) → mask → head (EWMA for drift, CUSUM for bias/spike per literature).
- [ ] Measure per-family recall@5%FAR on frozen cache vs v1/v2 + published baselines.
- [ ] **Kill bar:** no family clears baseline + 0.10 → strike v3, record fallback (family abstain, process-only ship).
- [ ] Commit.

### Task 4: Sensor stack (D-PCA → RBC-T²/PDC-Q → EBF)

**Why:** Cartocci Table I — RBC+D-PCA+T² 87/99/99 vs contributions+PCA 29/34; D-PCA the biggest lever; EBF 67→94% via +0.01/−0.005, clip [0,1], thr 0.2.

- [ ] RED: `tests/test_sensor_stack.py` — D-PCA augment shape; RBC-T² isolates synthetic single-sensor fault (argmax); PDC-Q challenger same bar; EBF counters (+0.01/−0.005, threshold 0.2, saturation) cut intermittent FAs while keeping true alarms.
- [ ] GREEN: `src/sensor_stack.py` — `dpca_augment`, `rbc_t2`, `pdc_q`, `ebf_filter`; sklearn PCA (98% variance PCs like the paper).
- [ ] Measure on twin sensor episodes: top-1 + FA-cut vs 0.26–0.33 baseline.
- [ ] **Kill bars:** sensor top-1 < 0.4 or FA-cut < 30% → strike; small-amplitude unreliability expected, abstain (not a strike cause if large-amplitude clears).
- [ ] Commit.

### Task 5: Transfer (held-5) + close-out

- [ ] Held-5 (ASM1/ASM2/B7P/B9/C6): per-machine top-1 + unknown-reject + abstain rate.
- [ ] Update `DIAGNOSIS_QUALITY.md`; full suite; fresh review; ship recommendation (abstain-gated).
- [ ] Commit docs-only.
