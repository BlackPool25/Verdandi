# Window-GBM runbook (locked operating point + monitoring)

Locked default: **global score >= 0.8, fire on first hot window (k=1),
one alert per episode with cooldown**. Measured on clean-battery OOF:
episode-hit 0.75, clean-episode FP 0.055, per-family hit 0.46-1.00
(breakdown/delay 1.00, quality 0.46 — the recall-first per-family set stays
available behind a flag for high-C_FN episodes only).

Why 0.8: prior-corrected neutral point at 3% prevalence (raw 0.5 in the lab
is true-0.24 in the plant); cost-dominant for any miss:alarm ratio below
~70:1. Dwell measured worse on every exchange (0.6/k1->k2: -0.06 hit for
-0.17 clean-FP vs 0.6->0.8: -0.08 for -0.27). Do not ship dwell without
measuring the 0.7/0.8 x k=2 grid above — done, dwell loses there too.

## Log from day one (per 128-tick window)

timestamp, raw_score, threshold, fire(0/1), dwell buffer state, alarm(0/1),
feature hash, operator ack/dismiss/escalate + latency, ground truth when
available (even delayed/weak). Aggregate daily.

## Signals and triggers

| signal | how | warn / re-tune / rollback |
|---|---|---|
| predicted-positive rate | daily mean vs binomial 95% band around lock baseline | 3 days outside band -> investigate |
| EM prevalence estimate (SLD on unlabeled scores) | weekly EM run | \|est - 0.03\| > 0.02 or 2x relative -> apply prior correction, re-tune |
| score distribution shift | weekly PSI on scores + feature PSI, baseline = cal set | PSI > 0.25 or 2 features > 0.25 -> re-tune candidate |
| calibration | ECE / reliability slope on labeled subset (>=100 labels/quarter) | ECE > 0.05 or slope outside [0.8, 1.2] -> recalibrate sigmoid |
| clean-alarm rate (heartbeats / known-clean periods) | FPR on clean proxy stream | > 2x locked target (> 0.12) sustained 7d -> rollback to previous thr or safe mode |
| cost realization | ack-rate, dismiss-rate, confirmed-miss reports | dismiss-rate > 75% for 2 weeks -> threshold too low; confirmed miss -> recompute r |

## Re-tune protocol

Freeze candidate on last 4 weeks labeled (or weakly labeled) data, require
conformal-risk-control certificate on a fresh calibration split, shadow
deploy 1 week, promote only if expected cost at re-elicited r beats current.
Rollback is automatic on the clean-alarm trigger — no meeting needed.

## Cost elicitation (ask the plant once)

"How many false alarms will operators tolerate to catch one extra real
event: 10, 50, 200?" The answer is r = C_FN / C_FP; alarm iff p > 1/(1+r).
r = 10 -> 0.09; r = 1 -> 0.5; r = 0.1 -> 0.91. Default assumption r in
[5, 30] keeps 0.8 optimal. Get r in writing before moving the threshold.
