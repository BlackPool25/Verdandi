# BUILD_BACKLOG — M0b→M5 (in order; each ends in a battery/spike re-run, never a narrative)

- **M0b detector sensitivity (first — only open bar).** Missed faults F-06/F-12/F-14 (R=0): per-fault
  sensitivity analysis → targeted fix (threshold-shape, feature, cal-window). Accept: battery re-run F1≥0.85
  (raw) + AC@1≥70% + flip<40% + no recall regression. Pointers: `spike/battery_rq1_rq2.py`, `REPORT_BATTERY.md`, `REPORT_M0.md`.
- **M1 detection hardening.** Versioned quantile-refit artifact + K2 drop>30pts alarm; PCMCI tau-2 evidence job
  (n≥800 floor); walk depth≤3 + top-k; DELAY/LOSS class gates (tau≥d window, imputation) as regression.
  Accept: K1/K2 gates green on 32-fault set.
- **M2 narration + model wiring.** Template+verifier + chain-cards + caps; Gemini/Ollama wiring (topology
  local-only); wiring-time grounding measurement. Accept: ≥95% or fallback stays armed (K3).
- **M3 replay + demo harness.** Subgraph-only replay; 5× same-seed 0-diverge gate; 20-fault battery as
  regression gate; <600s budget assert (K4/K5).
- **M4 waterfall UI + viva trail.** Copy EvidencePanel.tsx:246 + GraphView.tsx; battery JSONL → trail export
  (alarm → rank → sentences+triples → replay hash). Accept: trail per alarm, examiner-clickable.
- **M5 viva dry-run + calibration.** KQ close-out; recalibration gate per battery; dry-run defense of every
  kill/bar with numbers.

## Parked pivots (add iff trigger)
Minimal-twin fallback + detector-comparison study — trigger: K1 fires (AC@1<30%/flip>40%).
Learned-GDN — trigger: flip<20% + drift-spike gain. MP-discord — trigger: F1≥0.85 + faster/simpler (failed).
Free-LLM narration — trigger: ≥95% grounding with margin. ROCm GPU — trigger: clean driver spike in 1-wk box.
## Killed (no trigger — do not revive without L1 reclassification)
Blind discovery · Rust/Go core · pretrained weights · live stream · fixed thresholds · learned graph ·
Merlion-as-dependency · Jaeger backend · point-adjusted scoring · Uptake-$160 citation.
