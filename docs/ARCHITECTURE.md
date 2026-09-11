# ARCHITECTURE — anomaly-twin-trace (as stress-tested, not as imagined)

## Pipeline (batch sim, single laptop, CPU-only)
`Twin → Detect → Veto-mask → Walk → Narrate+Verify → Replay → Waterfall UI + viva trail`
1. **Twin:** hand-rolled SimPy 32-machine plant (Lines A/B/C 10/10/8 + assembly cell ASM0–2 + rework RWK0 + AGV pool/SBUF, mass-flow-conserved; FactorySimPy 0.1.0b3 API-unfit → rejected, ADR-0012).
    T=300/episode, clean cal window 120, seeded faults (7 classes spike/drift/bias/delay/loss/breakdown/quality, mag 4–7σ, dur 8–25),
    free ground truth. SeedSequence everywhere; PCMCI window floor n=800.
2. **Detect:** per-machine `max(q0.99, Q3+1.5·IQR)` on clean window. NO global fixed threshold (killed: SWaT
   0.886→0.281 [Tier1×2]). NO learned graph (GSL ineffective [Tier1]). NO MP-discord (F1 0.063, killed).
3. **Veto-mask (fixed topology prior):** VETO_ASM2 (ex-VETO_M5, identical 2×-margin semantics): ASM2 known-noisy needs 2× margin over runner-up for top-1.
4. **Walk:** depth≤3 + top-k prune (fan-out cap 8 assembly join; line-scale fan-out-5 baseline only); Kingman shed ≥80% richness-first, never detection/provenance.
5. **Causal (evidence-only, never production edges):** per-partition PCMCI ParCorr tau_max=2, pc_alpha=0.05,
    α=0.01; flip gate <40% per partition (14.4–30.3% line-scale baseline); lag-stability 0.889 line-scale baseline.
6. **Narrate:** template+verifier; provenance-id ≡ (fault-window, edge-id, detector-output) triple;
   ≤8s deadline → chain-cards fallback; per-run token/USD/iter caps ($47K-loop precedent).
   K3: >5% sans valid triple → fallback. Full-LLM grounding measured at M2 wiring.
7. **Replay:** subgraph-only, version-pinned RNG; 5× same-seed 0-diverge gate (K4).
8. **UI:** waterfall copied from EvidencePanel.tsx:246 + GraphView.tsx patterns; battery JSONL → viva-trail export.

## Data contracts (JSON)
`Alarm{id,machine,t_start,t_end,detector_output}` → `RankCause{alarm_id,ranked[(machine,score,edge_id)],AC@1}`
→ `Explanation{alarm_id,sentences[{text,triple|null}],grounding_rate}` → `Replay{alarm_id,seed,subgraph,diverge_bool}`.
Verifier rejects null/unresolvable triples in rate accounting; fallback serves chain-cards instead.

## Quality scenarios (ATAM, all with numeric measures)
- **S1 burst:** 20-fault battery + 50-coro contention → p99 ≤30s/fault, total <600s, AC@1≥70% (3.8ms / 17.7s / 0.80–0.8125 line-scale baselines).
- **S2 tail:** 15s model tail → ≤8s deadline → local fallback, 100% served (30/30 in 0.39s), grounding≥95%, +≤60s.
- **S3 malformed:** corrupt/truncated/injection → 100% rejection, 0 ungrounded pass, 0 egress, demo continues.
- **S4 determinism:** same-seed ×5 → 0 diverge (K4 gate).

## Forks decided (T1–T4)
T1 fixed-mask+stats (MP challenger killed; USAD second-line) · T2 constrained PCMCI tau-2/depth≤3 ·
T3 template+verifier+caps · T4 CPU-baseline (ROCm killed by driver triple-hit [Tier2×3]).
Revisit gates: learned/rich/free-LLM/GPU only on spike proof (see RFC).

## Boundaries
PCMCI short-run CONDITIONAL-GO (n≥800, flip gate) · walk GO-WITH-CAP+OOM gate · KV/VRAM N/A · fencing N/A
(no distributed state) · Kingman-80% ADOPT · quantile refit is a versioned artifact + K2 alarm (pre-mortem F1) ·
triple-resolution + mutation gate (F2) · SeedSequence + subgraph-only (F3).

## Non-goals (killed, with rationale)
Prod fleet twin · live stream · blind discovery · pretrained weights · Rust/Go core · learned-graph detection ·
GPU-dependent demo · safety-clearance authority · Merlion-as-dependency (archived Mar-2026, glue-only) ·
Jaeger backend (pattern-copy only) · point-adjusted scoring (inadmissible).
