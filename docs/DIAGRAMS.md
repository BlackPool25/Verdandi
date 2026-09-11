# DIAGRAMS — anomaly-twin-trace (Mermaid; text = truth, renders in GitHub/VSCode/docs)

> Conventions: numbers are measured (raw protocol) from `spike/REPORT_*.md`. Gates cite kill bars K1–K5.
> Decision records: `.opencode/blackboard/anomaly-twin-trace/DECISIONS.md` (ADR-0001–0012).

## 1. End-to-end pipeline (arch: `docs/ARCHITECTURE.md`, contracts: `docs/RFC.md`)

```mermaid
flowchart TD
    TWIN["Twin: hand-rolled SimPy line-6<br/>T=300, cal window 120, seeded faults<br/>SeedSequence, n>=800 floor"]
    DET["Detect: per-machine max(q0.99, Q3+1.5 IQR)<br/>NO fixed thresholds (killed)<br/>NO learned graph (killed)"]
    VETO["Veto-mask: FIXED topology prior<br/>M5 noisy needs 2x margin"]
    WALK["Walk: depth<=3 + top-k<br/>fan-out-5, shed>=80% richness-first"]
    PCMCI["PCMCI tau=2 evidence-only<br/>flip gate <40% (14.4-30.3%)<br/>NEVER production edges (K2)"]
    NAR["Narrate: template+verifier<br/>triple = window/edge/output<br/>deadline 8s -> chain-cards<br/>token/USD/iter caps"]
    REP["Replay: subgraph-only<br/>pinned RNG, 5x same-seed 0-diverge"]
    UI["UI: waterfall + viva trail<br/>Alarm -> rank -> sentences -> replay"]

    TWIN --> DET --> VETO --> WALK --> NAR --> REP --> UI
    WALK -.-> PCMCI
    PCMCI -.->|"lags feed veto window<br/>W=5=tau2+LAT3"| VETO
    NAR -.->|"K3: >5% ungrounded<br/>-> chain-cards"| NAR
    REP -.->|"K4: diverge<br/>-> subgraph-only"| REP
```

## 2. Twin topology + fault propagation (line-6; veto + walk overlaid)

```mermaid
flowchart LR
    M0["M0 source"] --> M1["M1"] --> M2["M2"] --> M3["M3"] --> M4["M4"] --> M5["M5 noisy<br/>veto: needs 2x margin"]
    F["Fault inject<br/>spike/drift/bias/delay/loss<br/>mag 4-7 sigma, dur 8-25"] -.-> M1
    F -.-> M3
    W["Walk depth<=3<br/>echo rule: downstream in<br/>[t-W-(m-u), t] attributed<br/>upstream iff score_u >= score_m"]
    M1 -.-> W
    M5 -.-> W
```

## 3. Template+verifier narration (K3 gate; spike: `spike/rq3_spike.py`, 1.00 grounded)

```mermaid
sequenceDiagram
    participant D as Detector/Veto
    participant T as Template narrator
    participant V as Verifier
    participant C as Chain-cards fallback
    participant O as Output trail
    D->>T: Alarm + ranked causes + edge_ids
    T->>V: Sentences + provenance triples
    alt every triple resolves to (window, edge, output)
        V->>O: Grounded explanation (rate >= 95%)
    else >5% unresolvable OR 8s deadline OR 429/drop storm
        V->>C: Fall back (spike: 30/30 in 0.39s)
        C->>O: Chain-cards (100% grounded by construction)
    end
    Note over V,O: 5/5 hostile rejected, 0 egress, caps enforced
```

## 4. Replay determinism (K4 gate; spike: `spike/spike_rq4_rq5.py`, 0-diverge 5x5)

```mermaid
flowchart TD
    S["Seed + subgraph slice"] --> R["Replay x5 same-seed<br/>PCG64/SeedSequence, pinned numpy"]
    R --> C{"diverge?"}
    C -->|"0 (measured)"| OK["Demo proceeds<br/>full battery 17.7s"]
    C -->|"any"| SUB["Subgraph-only mode<br/>full-graph never demo-critical"]
```

## 5. Kill-gate decision tree (bars: README; battery: `spike/REPORT_BATTERY.md`)

```mermaid
flowchart TD
    B["20/32-fault battery<br/>raw protocol"] --> K1{"K1: AC@1<30%<br/>OR flip>40%?"}
    K1 -->|"no: 0.80-0.8125 / 14.4-30.3%"| K2{"K2: F1 gap>30pts<br/>vs challenger?"}
    K1 -->|"yes"| PIV["PIVOT: cut learning<br/>topology+stats (parked)"]
    K2 -->|"yes: 67pts -> quantile mandatory<br/>MP rejected, learning CUT"| K3{"K3: >5% ungrounded?"}
    K2 -->|"no"| K3
    K3 -->|"no: 1.00 harness"| K4{"K4: diverge?"}
    K3 -->|"yes"| CC["chain-cards fallback"]
    K4 -->|"no: 0"| K5{"K5: ROCm sink>1wk?"}
    K4 -->|"yes"| SUB2["subgraph-only"]
    K5 -->|"no: CPU 17.7s"| COND["CONDITIONAL GO<br/>F1 ~0.73 disclosed"]
    K5 -->|"yes"| CPU["CPU-baseline (already default)"]
```

## 6. ATAM utility tree (ranked business-value x risk; oracle: `WORKER` purged, filed in DECISIONS)

```mermaid
flowchart TD
    G["Goal: viva-defensible trace<br/><10min one laptop"]
    G --> P1["1 Performance (H,H)<br/>demo<10min, <=3 steps, p99 bounded<br/>FAILS VIVA OUTRIGHT"]
    G --> P2["2 Accuracy-trust (H,H)<br/>F1>=0.85, AC@1>=70%, >=95%<br/>above-SOTA, must prove"]
    G --> P3["3 Availability-degrade (H,M)<br/>tail never kills demo<br/>local fallback always serves"]
    G --> P4["4 Modifiability (M,M)<br/>swap detector, edit mask,<br/>fallback without rewrite"]
    G --> P5["5 Security-safety (M,M)<br/>no egress, anonymized,<br/>human-only restart"]
    G --> P6["6 Determinism-testability (M,H)<br/>seeded replay, 5-seed flip"]
```

## 7. Claim lifecycle (Wieringa gate: truths are spiked, never voted)

```mermaid
stateDiagram-v2
    [*] --> Hypothesized: RQ filed
    Hypothesized --> Under_Investigation: defense+prosecutor
    Under_Investigation --> Corroborated: 2-domain Tier1-3 or spike PASS
    Under_Investigation --> Falsified: killer criterion met
    Under_Investigation --> Contested: split evidence
    Contested --> Corroborated: spike resolves
    Contested --> Falsified: spike kills
    Under_Investigation --> Unresolved: budget spent (gap-map, never silent)
    Corroborated --> [*]
    Falsified --> [*]: kept as NEVER invariant
```

## 8. F1 gap (measured; table fallback in `docs/SPIKES.md`)

```mermaid
xychart-beta
    title "F1: bar vs measured (raw protocol)"
    x-axis ["Bar 0.85", "Battery 0.734", "M0 ON 0.726", "Ceiling ~0.76", "AC@1 0.80"]
    y-axis 0 --> 1
    bar [0.85, 0.734, 0.726, 0.76, 0.80]
```

Reading: attribution (M0: +0.034 P, zero recall cost) closes ~1/5 of the gap; principled ceiling
~0.76; residual = sensitivity on 3/20 missed faults (F-06/F-12/F-14) → M0b build item. Recall 0.912–0.934
stays strong throughout — ship posture CONDITIONAL with disclosed precision.

## 9. Crucible run timeline (single session 2026-09-11; memory: MESSAGES.md bus)

```mermaid
gantt
    dateFormat YYYY-MM-DD HH:mm
    axisFormat %H:%M
    section Triage
    Elenchus ingest + project setup       :done, 2026-09-11 14:30, 2026-09-11 14:40
    Phase 1 sweeps (explore+librarian+prosecutor) :done, 2026-09-11 14:40, 2026-09-11 14:55
    section ATAM
    Oracle ATAM + T1-T4 forks + user picks :done, 2026-09-11 14:55, 2026-09-11 15:05
    section Spikes
    RQ3 narration + RQ4/RQ5 replay + T1 challenger :done, 2026-09-11 15:05, 2026-09-11 15:20
    RQ1/RQ2 battery (real path)           :done, 2026-09-11 15:20, 2026-09-11 15:30
    section Decide
    PR/FAQ + RFC + ADRs + scorecard + PLAN :done, 2026-09-11 15:30, 2026-09-11 15:40
    M0 echo (KILLED) + close-out DELAY/LOSS :done, 2026-09-11 15:40, 2026-09-11 16:10
```

## 10. Evidence tiers + 2-domain rule (research: `docs/RESEARCH.md`)

```mermaid
flowchart TB
    T1["Tier 1: proofs, benchmarks, IEEE<br/>FOUNDATIONAL (self-sufficient)"]
    T2["Tier 2: peer-reviewed + RFCs<br/>HIGH (needs context match)"]
    T3["Tier 3: retrospectives, postmortems<br/>CONTEXT-DEPENDENT"]
    T4["Tier 4: vendor benchmarks<br/>LOW (marketing until replicated)"]
    T5["Tier 5: blogs/forums/LLM asserts<br/>BANNED AS PROOF (seeds only)"]
    T1 --> T2 --> T3 --> T4 --> T5
    R["2-DOMAIN RULE: no claim -> EVIDENCE.md<br/>without >=2 independent Tier1-3 domains<br/>OR sandbox execution"]
```

## Diagram ↔ file index
| # | Diagram | Source of truth |
|---|---|---|
| 1 | Pipeline | `docs/ARCHITECTURE.md`, `docs/RFC.md` |
| 2 | Twin topology | `spike/battery_rq1_rq2.py`, `spike/closeout.py` |
| 3 | Verifier sequence | `spike/rq3_spike.py`, `spike/REPORT_RQ3.md` |
| 4 | Replay | `spike/spike_rq4_rq5.py`, `spike/REPORT.md` |
| 5 | Kill gates | `spike/REPORT_BATTERY.md`, `spike/REPORT_CLOSEOUT.md` |
| 6 | Utility tree | oracle ATAM (DECISIONS ADR-0003–0006) |
| 7 | Claim lifecycle | `PROTOCOL.md` §8 in blackboard memory |
| 8 | F1 gap | `spike/REPORT_M0.md`, `docs/SPIKES.md` |
| 9 | Timeline | blackboard `MESSAGES.md` bus |
| 10 | Tiers | `docs/RESEARCH.md` |
