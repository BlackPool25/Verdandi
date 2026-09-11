# Sprint Pack — M0b→M5

## 1. Sprint goal
Goal: Close the single open bar (F1≥0.85 via M0b sensitivity on the full factory flow) and wire narration→replay→UI→dry-run into a viva-defensible <10min CPU demo. | Capacity: 12–14wk semester; 6 stories; budget <600s demo, p99 ≤3 steps.

## 2. Stories
### Story M0b — detector sensitivity (only open bar)
problem-link: V1-§1 BTech team needs ranked trace + why-explanation; detectors force 30–60min triage.
traces-to: detection F1>=0.85 (direction: up)
- Acceptance: battery re-run raw F1≥0.85, no recall regression on F-06/F-12/F-14, full-plant coverage 32/32 machines, partitions × channels × classes (7 classes, 7 channels), per-partition flip<40%.
- Acceptance: AC@1≥70% + flip<40% per partition per class + p99 reported.
### Story M1 — detection hardening
problem-link: V1-§1 POV bytes above.
traces-to: trace AC@1>=70% @20 injected faults (up)
- Acceptance: K1/K2 green on 32-fault set; quantile-refit artifact + >30pts-drop alarm live.
- Acceptance: PCMCI tau-2 n≥800 floor + walk depth≤3 top-k; DELAY/LOSS class gates pass.
### Story M2 — narration + model wiring
problem-link: V1-§1 POV bytes above.
traces-to: explanation groundedness>=95% sentences with provenance id (up)
- Acceptance: wiring-time grounding ≥95% or chain-cards armed (K3); triple ≡ (fault-window, edge-id, detector-output).
- Acceptance: ≤8s deadline → local cards 100% served; caps enforced.
### Story M3 — replay + demo harness
problem-link: V1-§1 POV bytes above.
traces-to: end-to-end demo<10min on team GRE/laptop (down)
- Acceptance: 5× same-seed 0-diverge gate (K4); subgraph replay preserves whole-flow context.
- Acceptance: 20-fault regression <600s (17.7s line-scale baseline) + p99 reported.
### Story M4 — waterfall UI + viva trail
problem-link: V1-§1 POV bytes above.
traces-to: explanation groundedness>=95% sentences with provenance id (up)
- Acceptance: per-alarm waterfall (EvidencePanel + GraphView patterns) examiner-clickable with full-plant cause path.
- Acceptance: trail export per alarm: rank + sentences+triples + replay hash + battery numbers.
### Story M5 — viva dry-run + calibration
problem-link: V1-§1 POV bytes above.
traces-to: detection latency<=3 timesteps (down)
- Acceptance: dry-run defends every kill/bar (K1–K5) with numbers incl. full-flow coverage.
- Acceptance: kill criteria re-checked; pivots trigger-armed, kills unrevived.

## 3. Definition of Done
- [ ] All acceptance lines verified | - [ ] traces-to metric measured
- [ ] No UNMAPPED scope added | - [ ] Kill criteria (V1-§5) re-checked

## 4. Traceability matrix
| metric (V1-§2 verbatim) | story |
|---|---|
| detection F1>=0.85 (up) | M0b, M5 |
| trace AC@1>=70% @20 injected faults (up) | M0b, M1 |
| detection latency<=3 timesteps (down) | M1, M3, M5 |
| end-to-end demo<10min (down) | M3, M4 |
| explanation groundedness>=95% sentences with provenance id (up) | M2, M4 |
