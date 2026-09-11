# ADR-0011: M0 Echo-Attribution — KILLED

Status: accepted
Date: 2026-09-11
Supersedes: ADR-0009 (M0 echo-aware attribution direction)
Amends: PLAN.md Addendum 2026-09-11 (M0 echo-attribution KILLED)

> Immutability note: ADRs are never edited after acceptance. Further change requires a new ADR that supersedes this one.

## Context

ADR-0009 set the single open bar: M0 echo-aware attribution to F1 >= 0.85 (raw), with AC@1 >= 70% and flip < 40% held. The F1 gap was diagnosed as precision (downstream echoes inside the PCMCI lag window), not recall. The prescribed fix was a suppression rule with no new infra: re-run the 20-fault battery and pass.

Rule under test (spike/m0_echo.py, real 20-fault path, wall 8.4s): suppress a downstream win when upstream score >= downstream within [t-W-(m-u), t], W=5=tau2+LAT3. Report: spike/REPORT_M0.md.

## Options

1. Ship the rule as the F1 closer.
2. Iterate principled variants (score-less windows).
3. Kill attribution as the closer; re-scope M0 to detector sensitivity.

## Outcome

KILL echo-attribution as the F1 closer. The rule worked but has a principled ceiling below the bar:

- dP +0.034 on 14/20 faults, dR exactly 0, non-vacuous (inversion 0.726 to 0.699).
- Principled-variant ceiling approx 0.76 (score-less windows lose recall, rejected).
- F1 0.726 misses 0.85 by 12.4pts.
- Residual is structural, not attribution: 3/20 faults at R=0 (F-06/F-12/F-14 sensitivity, nothing to attribute) plus M5 noisy-channel FPs plus echo tails.
- Side gain kept: AC@1-lat3 0.65 to 0.80.
- OFF-baseline jitter 0.734 to 0.700 cross-run is hash()-seed noise; within-run delta is valid.

No bar softened. F1 >= 0.85, AC@1 >= 70%, flip < 40% all stand.

## Consequences

- M0 re-scoped as build item M0b detector-sensitivity: missed-fault analysis first, no new infra, no more attribution work.
- Ship posture stays CONDITIONAL at F1 approx 0.73 with disclosed precision plus recall/rank viva framing (PR/FAQ failure-reason #1 path).
- SIM_SPEC documents why the old 0.45^lag echo is gone and mandates flow-conserved propagation instead.
