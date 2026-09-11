# RFC: anomaly-twin-trace (Google-style)

## Context
Elenchus brief `ELENCHUS_DISCOVERY.md` (slug anomaly-twin-trace): viva-graded BTech team needs ranked causal trace + why-explanation per factory-twin alarm. Crucible evidence: `EVIDENCE.md`, `contradictions-map.md`, spikes in `spike/` (REPORT_BATTERY.md, REPORT_RQ3.md, REPORT.md).

## Goals
- Ranked upstream cause ≤3 steps per alarm; AC@1≥70%@20 faults (battery: 80%).
- Why-explanation with ≥95% triple-resolved provenance (template-level spike: 1.00).
- Seeded subgraph replay, 0-diverge; demo <10min CPU laptop (battery: 17.7s).
- Kill bars K1–K5 enforced as regression gates.

## Non-Goals
- Prod fleet twin, live streaming, blind discovery, pretrained-weight reuse, Rust/Go core, learned-graph detection, GPU-dependent demo, safety-clearance authority.

## Detailed Design
- **Twin:** FactorySimPy line-graph (6 machines), T=300/episode, clean cal window 120, seeded faults (free ground truth). SeedSequence everywhere; min stable n=800 floor for PCMCI windows.
- **Detect:** per-machine `max(q0.99, Q3+1.5·IQR)` on clean window + FIXED veto-mask (M5-noisy needs 2× margin). M0 adds echo-aware attribution (suppress downstream inside lag window) to lift P 0.614→bar.
- **Causal (evidence-only):** constrained PCMCI ParCorr tau_max=2, pc_alpha=0.05, α=0.01; flip gate <40% (battery 14.4%); lag-stability 0.889. Production edges NEVER learned — K2 cut learning-based detection.
- **Walk:** depth≤3 + top-k prune (fan-out-5 measured); Kingman shed ≥80% richness-first.
- **Narrate:** template+verifier; provenance-id ≡ (fault-window, edge-id, detector-output); ≤8s deadline → chain-cards; per-run token/USD/iter caps; K3 >5% → fallback.
- **Replay:** subgraph-only, version-pinned RNG; 5× same-seed 0-diverge gate (K4).
- **UI:** waterfall copied from EvidencePanel/GraphView patterns; viva-trail export (battery JSONL → trail).

## Interface contracts (JSON)
- `Alarm{id, machine, t_start, t_end, detector_output}` → `RankCause{alarm_id, ranked[(machine, score, edge_id)], AC@1}` → `Explanation{alarm_id, sentences[{text, provenance triple|null}], grounding_rate}` → `Replay{alarm_id, seed, subgraph, diverge_bool}`. Verifier rejects any sentence with null/unresolvable triple when rate accounting runs (fallback path serves chain-cards instead).

## Alternatives Considered & Why Rejected
1. **Learned-GDN detector** — GSL ineffective [Tier1]; torch absent; no short-run evidence. Rejected; revisit iff flip<20% + drift-spike gain.
2. **Matrix-profile discord detector** — 2-domain Tier1 challenger, but battery: F1 0.063, AC@1 0.20, 1700× slower. Rejected as detector (K2 fires); pattern retained for offline validation only.
3. **Free-LLM narration** — OpenRCA2.0 38.5% ungrounded [Tier1] + $47K-loop risk. Rejected; template+verifier + caps + fallback.

## Open questions (empirical, to M0–M2)
- Echo-attribution lift to F1≥0.85 (battery re-run decides). Full-LLM grounding % at wiring time. tau-2 hold on new fault classes (flip gate).
