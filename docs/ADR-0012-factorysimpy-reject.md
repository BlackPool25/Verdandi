# ADR-0012: FactorySimPy Rejected — KEEP-HANDROLLED SimPy

Status: accepted
Date: 2026-09-11
Supersedes: nothing (close-out of pre-build triage)
Amends: PLAN.md Addendum 2026-09-11 (Close-out, zero known holes)

> Immutability note: ADRs are never edited after acceptance. Further change requires a new ADR that supersedes this one.

## Context

Close-out spike (spike/closeout.py, wall 3.1s) had two jobs: confirm DELAY/LOSS fault classes survive K1 per-class, and evaluate FactorySimPy as a replacement for the hand-rolled SimPy twin. Report: spike/REPORT_CLOSEOUT.md.

Battery numbers (verbatim): DELAY F1 0.670, AC@1 5/6, flip 24.2%; LOSS F1 0.739, AC@1 5/6, flip 30.3%; base reproduces (0.739/0.80/14.4%); totals 32 faults F1 0.725, AC@1 0.8125, p99 2.6ms. K1 survives per-class x3 and globally. RCAEval blind-spot does NOT reproduce. Class mitigations noted (tau>=d window, better imputation) ride as M1/M5 regression gates. Per-class MP re-run skipped (dead path, waste).

## Options

1. Adopt factorysimpy==0.1.0b3 as the twin framework.
2. Keep hand-rolled SimPy 4.1.2 twin (pinned).

## Outcome

KEEP-HANDROLLED (pinned). factorysimpy==0.1.0b3 installs (PyPI, MIT) and runs a 3-machine line in 0.01s, but it is API-unfit: discrete-only counts, no signal-trace API, no seeded-fault params, no RNG hooks, so strictly MORE glue than the hand-rolled twin. Verdict recorded in DECISIONS.md ADR-0012 and SIM_SPEC section 1 (hand-rolled SimPy only, real simpy.Resource / simpy.Store objects, not abstract delays).

## Consequences

- Build implements SIM_SPEC alone; spike/ stays quarantine, never merged.
- Zero known pre-build holes remain; pre-build triage COMPLETE.
- No bar softened: F1 >= 0.85, AC@1 >= 70%, flip < 40%, p99, <600s wall, grounding >= 95%, 5x same-seed 0-diverge all stand.
