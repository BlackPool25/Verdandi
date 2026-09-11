# contradictions-map.md — Contested items (Phase 1 adjudication)

| ID | Claim | Defense (for) | Prosecutor (against) | Tier | Resolution path |
|---|---|---|---|---|---|
| C1 | ≥95% sentences w/ provenance (K3) | TAMO-FoA/KRCA tool-grounding pattern [T1+T2, 2-domain] | OpenRCA2.0 20.7% exact / 38.5% ungrounded https://doi.org/10.48550/arxiv.2606.27154 [T1]; RF-03 provenance confusion [T1]; KRCA lost-in-middle; 76.3%<95% | T1 both sides | SPIKE RQ3: template+verifier pipe, 100% malformed/boundary rejection, mutation gate; K3 fires → chain-cards |
| C2 | PCMCI stable on short runs, flip<40% (K1) | Contract + Bagged-PCMCI+ P/R [T1/T2] | Spurious under autocorrelation https://proceedings.mlr.press/v124/runge20a.html [T1]; Sandia FPR↑ [T1]; 60–85pt warning issue #482 [T2]; flood-graph instability | T1 both sides | SPIKE RQ2: 5-seed lag sweep, edge-flip metric; K1 fires → topology+stats |
| C3 | AC@1≥70%@20faults | KRCA 0.88/0.79 [T2→1] | RCAEval best Avg@5 0.46–0.54 + BARO DELAY/LOSS death https://doi.org/10.48550/arxiv.2412.17015 [T1]; Signal-Loss/Infra/Semantic blind spots [T1] | T1 both sides | SPIKE RQ1/RQ2: 20-fault battery defines ceiling; above-SOTA must prove or K1 |
| C4 | Same-seed replay diverges→? (K4) | DT-Drive 100% deterministic pattern | FactorySimPy discrete-only/static [T2]; SimPy single-thread strain [T3]; numpy default_rng nondet w/o SeedSequence [T2]; no diverge incident = gap not proof | T2 | SPIKE RQ4: version-pinned RNG, subgraph-only replay, diverge test |
| C5 | PyRCA walk at depth≤3 scales | Capped-walk design | Graph-build worst-case exponential (own blog) [T2] | T2 | SPIKE: 10×-ingress saturation + OOM kill-gate |
| C6 | FactorySimPy suffices semester | Ownership zeroes upkeep (Elenchus) | Discrete-only/static/expertise-gated ext. [T2] | T2 | SPIKE RQ4/RQ5: <10min seeded run decides |

Caps invariant (from $47K/264h loop [T2]): per-run token/USD/iteration caps mandatory in every spike + demo.
