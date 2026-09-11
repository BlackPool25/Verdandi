# ADR-0013: 32-Plant Twin, Rename to Verdandi, and SOTA Challenger Verdicts

Status: accepted
Date: 2026-09-11
Supersedes: nothing (extends ADR-0011/ADR-0012 and SIM_SPEC plant scope)
Amends: SIM_SPEC (32-machine normative plant); project rename chain

> Immutability note: ADRs are never edited after acceptance. Further change requires a new ADR that supersedes this one.

## Context

Two threads converged on 2026-09-11. First, Oracle audit fix #2: the 6-machine spike twin used signal-copy echo (0.45^lag) with no mass conservation, no blocking/starving, and no rework or shared-resource contention, so a detector tuned on it learns a signature that cannot exist in the plant. Second, SOTA research 2026-09-11 on detector challengers (GDN/USAD/DLinear raw-F1), causal discovery (bagged-PCMCI+ PMLR236, DYNOTEARS, neural Granger), and NLI verifiers (AGREE/VeriTrail/TRACER) plus ID-traceability requirements. This ADR locks the plant decision, the rename, and the research verdicts. Bars from ADR-0011/ADR-0012 stand, never softened.

## Options

Plant: (a) keep 6-machine signal-copy twin; (b) 32-plant flow-conserved twin with per-partition PCMCI.
Name: (a) anomaly-twin-trace; (b) ForgeTrace; (c) Verdandi.
Detectors: GDN-light / USAD-small / DLinear ensemble vs MP-discord vs quantile/IQR status quo.
Causal: bagged-PCMCI+ vs DYNOTEARS vs neural Granger vs tau=2 PCMCI status quo.
Narration: NLI critic (deberta-v3 + ID-traceability) vs pure-LLM narration vs template+verifier status quo.

## Outcome

1. 32-plant ADOPTED (normative in SIM_SPEC): lines A/B/C 10/10/8 plus ASM cell (ASM0 kitting, ASM1 join, ASM2 test) plus RWK0 rework loop plus shared AGV pool, totalling 32 machines. True coupling via WIP movement, buffer occupancy, BLOCKED/STARVED/DOWN states, and part-carried quality flags replaces 0.45^lag echo. Causal evidence runs per-partition PCMCI (line-A, line-B, line-C, cell; cross-partition only at tails-to-ASM0 AGV links and ASM2-RWK0-ASM0 rework), never full-32-node discovery.
2. Rename ADOPTED: anomaly-twin-trace to ForgeTrace to Verdandi (Norn of what-is). Elenchus slug frozen in Crucible sources; memory root and history keep the old slug.
3. Research verdicts:
   - GDN-light / USAD-small / DLinear ensemble ADOPTED as the M0b challenger path. MP-discord stays guardrail only (F1 0.063, killed as detector).
   - Bagged-PCMCI+ ADOPTED as primary causal evidence (drop-in per partition). DYNOTEARS second opinion only. Neural Granger REJECTED.
   - NLI critic (deberta-v3 + ID-traceability) ADOPTED into the M2 verifier. Pure-LLM narration stays rejected; template+verifier primary with chain-cards fallback and K3 gate (>5% ungrounded to fallback) unchanged.

## Consequences

- Build twin implements SIM_SPEC sections 2-10 alone; no 0.45^lag copy anywhere; battery wall <600s with per-partition caps.
- M0b evaluates the ensemble challenger against quantile/IQR on the missed-fault set first (F-06/F-12/F-14 sensitivity); promotion needs the same bars (F1 >= 0.85, AC@1 >= 70%, flip < 40%).
- M2 wires the NLI critic inside the verifier; grounding >= 95% bar and caps ($0.005 / 2.5k tok / iter) unchanged.
- Rename propagates to docs and packaging; Crucible-era sources and the Elenchus slug stay untouched for traceability.
