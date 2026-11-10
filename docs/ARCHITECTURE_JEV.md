# Jev-Decision Architecture (classifier-free diagnosis + typed reports)

Status: APPROVED for implementation (user decisions 2026-11-11: TypeSafe Jev,
API available, Jev decides full 26x7+null, null->abstain, layered card+dossier).

## 1. Pipeline

```
detect (frozen v7, 0.800@0.032)
  -> candidates (radius-2) + onsets + flow counters + calibrated confidence
  -> EVIDENCE PACKET (schema v1, every field has an id)
  -> Jev decider (API): {machine: choice[26+null], family: choice[7+null],
     severity: choice[SEV1-5]} + probabilities + criteria text (versioned)
  -> threshold in OUR code (null or conf < tau -> abstain report)
  -> reporter: operator card + engineer dossier (LLM phrases only, temp 0,
     constrained schema, numbers copied verbatim with evidence IDs)
  -> offline fallback: template builder (deterministic, always available)
```

No 26-way GBM, no family head in the loop. Ranker scores survive only as
evidence fields (they are measurements, not verdicts).

## 2. Evidence packet schema v1 (per incident)

- ids: `det-{ep}-{tick}` detection; `ev-{machine}` per-machine evidence;
  `path-{i}` ranked paths; `conf` calibrated confidence + T.
- fields: trigger tick, anchor, ranked paths (nodes+scores+probs), per-machine
  {onset, onset_kind, own_state, eweight, flow counters}, sentinel agreement,
  family-head scores (advisory only, labeled as such).
- determinism: builder is pure (episode df + edges -> packet); replay-hash tested.

## 3. Jev question spec v1 (criteria from failure physics)

- machine: "which machine originated the fault?" criteria per propagation
  role (origin shows earliest onset + DOWN/counter states; STARVED-only is
  symptom, never origin).
- family: "which fault family?" criteria from channel coupling (sensor =
  single-channel obs deviation, current unmoved; process = obs+current
  jointly; loss = count/flow consequence; quality = sink rejects; delay =
  cycle stretch; breakdown = DOWN).
- severity: SEV1 line-down ... SEV5 single-window transient (rule-mappable;
  Jev confirms).
- null allowed on every question; threshold tau in our code.

## 4. Reporter contract (faithfulness)

- Every claim cites an evidence ID. Numbers copied verbatim from packet/Jev
  output, never computed by the phraser. Schema-constrained decoding;
  temperature 0. Template fallback when API unreachable (deterministic).
- Eval (fixed episode set): faithfulness (claims entailed by cited IDs),
  citation precision/recall, category accuracy vs GBM 0.671 baseline,
  null rate vs coverage. LLM-judge aggregated over runs.

## 5. What this kills / keeps

- KILLS as verdicts: 26-way teacher, family head, specialists, sensor stack.
- KEEPS as evidence: ranker scores, family scores (advisory), flow counters,
  calibration gate, path ranker, abstain logic.
