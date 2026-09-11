# SPEC — functional specification (what the system does, actor by actor)

## Actors
- **Team (builders/operators):** runs twin, injects faults, reads ranks + explanations, exports trails.
- **Professor/examiner (buyer, marks):** probes any alarm live; needs replay evidence + provenance per sentence.
- **Lab infra (blocker):** one CPU laptop, no GPU rights, no network trust.

## Functional requirements
- **FR-1 rank:** every alarm returns ranked upstream causes, depth ≤3 steps from symptom (AC@1≥70%@20f).
- **FR-2 explain:** every flag carries sentences; ≥95% resolve to a (fault-window, edge-id, detector-output)
  triple, else chain-cards fallback serves instead (K3).
- **FR-3 replay:** any alarm replays from seed + subgraph with 0-diverge proof (K4).
- **FR-4 waterfall UI:** per-alarm water view (detector output → veto → walk → narration → replay hash),
  patterns copied from EvidencePanel.tsx:246 + GraphView.tsx.
- **FR-5 viva trail:** one export per alarm: rank + sentences + triples + replay hash + battery numbers.
- **FR-6 demo budget:** end-to-end <10min on CPU (measured 17.7s battery + ≤60s narration + UI).
- **FR-7 degrade:** model tail → local fallback in ≤8s, 100% served; 10× ingress sheds richness, never provenance.
- **FR-8 caps:** every run bounded by token/USD/iteration caps ($47K-loop precedent).
- **FR-9 no authority:** twin NEVER issues safety-restart clearance (human-only).

## Alarm lifecycle
`injected (seeded, free truth) → detected (quantile/IQR) → vetoed (fixed mask) → walked (depth≤3) →
narrated+verified (triple gate) → replayable (seed+subgraph) → trailed (export)`.
Any gate breach fires its kill-bar path (TECHNICAL.md fallback matrix), never a silent pass.

## UI field spec (waterfall card per alarm)
`alarm_id · machine · t_start/t_end · detector_output · ranked[(machine, score, edge_id)] ·
sentences[{text, triple|null}] · grounding_rate · replay{seed, subgraph, diverge_bool} ·
battery_ref (F1/AC@1/flip run id)`.

## Viva-trail export schema (JSON, per alarm)
`{alarm_id, rank_cause:{ranked, AC@1_ref}, explanation:{sentences, grounding_rate},
replay:{seed, subgraph, diverge:false, runs:5}, evidence:{battery:F1/AC@1/flip/p99, spike_ids}}`.

## Demo runbook (<600s budget)
1. Boot twin + cal window (120 steps) — asserts clean. 2. Fire 20-fault battery (17.7s) — asserts
   AC@1≥70%, flip<40%. 3. Pick examiner's alarm → show rank (≤3 steps). 4. Read explanation → every
   sentence triple-resolves (spot-check 3). 5. Replay same-seed ×2 live → identical. 6. Inject DELAY+LOSS
   sample → rank holds (K1 class gates). 7. Show fallback: kill model call → chain-cards in <8s.
   Total ≈ 3–5 min; headroom 2×. Any assert fails → state the kill-bar + parked pivot (viva-proof honesty).
