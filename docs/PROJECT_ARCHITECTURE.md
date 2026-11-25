# Verdandi — Complete Architecture, Routing, State & Roadmap

> Single-file reference. Base: `m0b-t-build @ dfd2839`. Measured-only: every number carries n/seed/lineage or is labeled UNMEASURED. Stale claims are marked struck, not deleted.

## 1. What this project is

Verdandi is a factory-twin diagnostic pipeline: for every alarm raised by a 26-machine cellular factory twin, it returns a **ranked upstream cause**, a **why-explanation with cited evidence**, and a **seeded replay proving it** — on one CPU laptop, end-to-end under 10 minutes. It lives at ISA-95 Level 3 (supervisory advisory). It **never** issues safety or restart commands to PLCs (REQ-009/SPEC FR-9); safety interlocks stay hardwired and authoritative. An hallucinated clearance could kill people — so the twin has zero control authority by construction.

Current status: pre-ship. Ship bars are F1 ≥0.85, AC@1 ≥70%, flip <40%, grounding ≥95%, 0-diverge replay. Honest position: retrieval is strong in-grid, calibration and scale proofs are still open (see §15).

## 2. Simulation twin (`src/twin.py`)

- **Engine:** hand-rolled discrete-event SimPy 4.1.2 model (FactorySimPy rejected per ADR-0012 — API-unfit). 26 machines, Topology-A: feeder lines A (6), B (7, redundant midsection B7P/B7S), C (5, fast feeder) → AGV pool (cap 3) + shared buffer SBUF (cap 30) → assembly cell ASM0→ASM1→ASM2 → inspection INSP0 (hold 3) → pack line PKG0–2, with rework loop RWK0 (max 2 passes) and scrap.
- **Episode:** T=300 ticks/machine, calibration window 120, warmup 15. Clean runs plus seeded faults (7 classes: spike, drift, bias, delay, loss, breakdown, quality; mag 4–7σ, dur 8–25).
- **Determinism:** 6 isolated NumPy `SeedSequence`→PCG64 streams (noise, placement, dropouts, AGV transit, breakdowns, repairs). Same seed ⇒ bit-identical record (SHA-256 `replay_digest`). Mass-flow conserved.
- **Why a twin, not a dataset:** static CSVs (SWaT etc.) admit no counterfactual replay, have fixed topology, and published scores are contaminated by point-adjustment (Kim et al. AAAI 2022: random noise beats SOTA under PA). Verdandi scores raw point-wise, PA-OFF, always.

## 3. Fault physics and cascade mechanics

Faults are injected in `src/config.py`/`twin.py` as observation-only (spike/drift/bias/loss: signal only, plant physics preserved) vs physical (delay/breakdown/quality/wear: cycle/state/flow altered). One root failure fans out both ways:

- **Downstream starvation:** A2 breakdown → buffer A27 drains (cap 3, ~15 steps) → A7 STARVED → A8 → A9 → AGVs idle → SBUF starved of component A → ASM0 starved (~t+35). 50–100 SCADA alarms from one root cause.
- **Upstream backpressure:** A2 down → buffer A1 fills → A1 BLOCKED → A0 BLOCKED → line infeed halts.
- **AGV contention:** 3-vehicle pool; fast lines can starve others of transport with zero machine faults.
- **Quality rework:** ASM2 defect spike (2%→30%) → INSP0 rejects → RWK0 loop overflows → ASM0 blocked.

The operator's problem: the screen flashes at ASM0/A7/INSP0; the cause is at A2. Verdandi's job is to walk the cascade backwards to A2 with proof.

## 4. Data contracts (frozen)

- **Schema v6** (`TWIN_SCHEMA=6`, `CODE_VERSION=twin-2.5.0-topology-A`): 10 tick keys (`step, states[32*], obs, throughput{0,1}, buffers[31], sbuf_level, events_at_k[], faults[], quality{sparse}, currents`), 6-key header (`seed, T, sbuf_stats, flow_stats, c7tail_final, energy`). No `temperature` key (twin discards `_temp`; bridge rejects it). Quality is sparse parts-last join. Throughput domain is {0,1} (twin wins over SIM_SPEC §8).
- **Storage:** offline Parquet, no SQL. **Transport:** FastAPI sim_bridge — `POST /episode` (precompute + digest) → `GET /stream?episode_id&from_step` (SSE header + 300 ticks, idempotent resume). Live stream is a demo viewer (SIM_SPEC waiver), not a production claim. Episode budget <2MB.
- **Diagnosis side-channel:** evidence packet v1 (`src/packet.py:emit_packet`) — `det-{ep}-{trigger}` packet id, per-machine `ev-*` trace rows, ranked `path-*` paths, `verdict: diagnosed|abstain`, confidence + flow. No ground truth inside. Card/dossier JSON + markdown are file artifacts, never tick keys.

## 5. Detection

- **Per-machine quantile/IQR** on clean-RUN calibration (`max(q0.99, Q3+1.5·IQR)`), never global fixed thresholds (SWaT collapse 0.886→0.281 proves why). MP-discord killed (F1 0.063, 1700× slower).
- **Three split heads** (PR #16/17): H_obs (continuous: vibration/temp/current), H_state (discrete: dwell, tput-lag, down-runs, stale-hold, buffer occupancy — catches delay/loss/breakdown with |z|≈0.67σ where signal detectors score R=0), H_part (flow/quality: degrade/reject counts, rework passes, funnel rate).
- **Fixed veto-mask** (VETO_ASM2: noisy ASM2 needs 2× runner-up margin for top-1). **K2 armed:** F1 drop >30pts vs stored quantile ⇒ quantile mandatory, learning cut.
- **Multi-scale:** neutral dyadic bank {1..64} + global Hilbert envelope (GES2N-v1), no window-local Gibbs artifacts.

## 6. Calibration and the abstain gate

- **Mechanism:** post-hoc temperature T + Platt (a,b) on held-out/OOF scores (`src/confidence.py`: golden-section T, Newton-IRLS Platt, 15-bin ECE, coverage curve, threshold picker). Temperature preserves argmax (accuracy-invariant); Platt adds intercept for base-rate shift. Small-n ⇒ Platt over isotonic (isotonic needs ≥100/class).
- **Measured (teacher window OOF, n=96000):** T=2.58, NLL 2.465→1.366, ECE 0.246→0.034 (−86%). Risk 0.300@cov1.0 → 0.186@0.7. Held-5 transfer: forced 0.327, τ=0.739, coverage 0.337 @ risk 0.3 ⇒ **66% abstain on unseen machines at same risk**.
- **Serving rule:** τ=0.739 (held-5 row) only — τ=0.080 (all-windows) gates nothing and must never be served. Gate sits after rank, before `build_report`; below τ ⇒ abstain card (`low-confidence-calibrated`), conf+τ persisted per incident. Kill bar: forced top-1 shift >0.01 ⇒ stop. SGR/exact-binomial bound logged alongside for later promotion. Ranker-level recalibration (stage2-oof.npz + exclude-held retrain) is scheduled follow-up, not a gate blocker.

## 7. Attribution and ranking

- **Stage-1 teacher** (majority vote over window posteriors): top-1 0.654 rerun (n=2712; 0.671–0.674 pre-regen). **Stage-2 LambdaRank** (26 candidates/episode, 3-fold episode-grouped CV): votable top-1 **0.667 rerun** vs bar ≥0.70 — V1 calibrated 0.667, V2 trunc-2 0.665 → **STRUCK after max 2 variants** (Tasks 2/5). Pooled (silent-as-misses) 0.458–0.461; silence concentrates in loss + quality.
- **Rerank plan (max 2 variants, then strike):** (1) calibration-aware rerank on stage2-oof (post-hoc, minutes); (2) only if needed, per-family heads or pairwise/truncation config. Identical episodes/CV/groups; votable + pooled dual reporting. Struck: soft vote 0.672, weighted 0.663, vote-free 0.355, hybrid +flow +0.000 (57.8% nonzero flow cols, identical to 3 decimals — row-form is the wrong carrier).
- **v2 physics firing:** CONFIRMED on full 7-family mix (Task 3, 2026-11-25): obs+flow ON 0.719 vs obs-only OFF 0.680 @ clean-fire 0.063 vs 0.080, thr 0.7 (same direction @ 0.5; n=700+300/arm, seed-identical grids, `docs/SIM_BASELINE.md` full-mix verdict). Focused quality+loss win (+0.185) was the precedent; general firing-head claim now kept. Ship/abstain dispositions unchanged.
- **Tev decider (local `tev1:4b`, temp 0, think off):** machine 0.094 (5/53) / family 0.132, n=60 pinned seed — **STRUCK as decider** (Task 4; SC confirms, B7S-default bias documented); kept for phrasing only, never piped into ranker.

## 8. Causal paths (diagnostic-only)

`kbest_paths` (geomean × coherence + support, max_len 4, delay-discounts-never-vetoes) + `route.py` DAG reachability. Measured: re-run ranked arm on regen battery: root-hit@1 0.072, subseq@3 0.287 (n=167 — regen moved the baseline; old 0.162 stale, do not cite); flow-teleport PPR (α=0.85) Δ+0.000 with flips washing out → stays diagnostic-only, never the verdict path.

## 9. Packet → decision → report routing (how an alarm flows)

`diagnose_incident(seed/fault)`: onsets → radius-2 candidates → rank → path → link → `emit_packet` → (calibrated conf gate) → `jev.decide` (key-gated; `JevUnavailable` ⇒ template) → `build_card` + `build_dossier` → incident store. Every claim carries an evidence ID from the packet; the reporter asserts it (`uncited claim` fails). Abstain shapes: `silent-clean` (no onsets, never a guess), `low-confidence(-calibrated)`, `single-node`, sensor verdicts. Dossier drills trace/paths/onsets/evidence IDs; flow/teleport numbers are diagnostic annotations, never verdict inputs. Grounding ≥95% or K3 fires ⇒ chain-cards fallback (≤8s deadline, 0 ungrounded pass, 0 egress).

## 10. Frontend (`/sim` React viewer — the ONLY frontend)

Single `EventSource` per mount (`streamController` + `?from_step` resume), one shared playback cursor feeding TopologyView (dagre layout, memoized per-tick patches), MachinePanel/BufferBars, MachineGrid (selection only), StripChart (Canvas + Zustand transient subscribe, badges 4–10Hz, render-counter spec: 0 chrome renders/tick), EventFeed (cursor-following, cap 100, family filter, `!` glyphs — color never the sole signal), ControlsBar (seed/fault-post/playback). `CausalProofCard` (deterministic ≤3-hop physical chain, ORIGIN badge, step-to-origin) and `NarrationBar` (priority template ladder, dwell, aria-live, click-to-inspect) are the existing diagnosis surfaces. **Integration is additive:** new `DiagnosisCard` panel (file/textarea packet JSON in → what/where/severity/action + evidence chips wired to `onSelect`/`onStepTo`), `DossierView` tabs, abstain banner (reason + coverage + action) — same props/patterns, default-off sections. **Gates (T12):** palette audit (Sweetie16), scope grep, `tsc`, vitest (incl. render-counter + reduced-motion + panel-equality), `src/`-untouched fidelity, bridge pytest/ruff/mypy/pip-audit. No Streamlit, no new framework, no tick-key additions, theme/UX untouched.

## 11. Bridge, Docker, replay, testing

- **Bridge** (`services/sim_bridge`): `POST /episode`, `GET /stream`, `GET /schema`, frozen v6 validation. **Docker:** `api:8000` (healthy-gated) + `web:19104`, `verdandi-artifacts` volume. Verified live: schema intact, episode+stream round-trip, viewer 200.
- **Replay:** subgraph-only, version-pinned RNG, 5× same-seed 0-diverge (K4). **Testing:** 696 test functions across 116 `test_*.py` files (branch-measured 2026-11-25 via `Select-String 'def test'`; pytest-collected count may differ), markers k1–k5/battery/adversarial/mutation; 61+25 frontend vitest/playwright; brutal gates (`check_gates.py`); 10/10 hostile-input rejection; mutation non-vacuity; PR/FAQ failure-reason ledger. (README §Testing still shows 34 files/300+ — stale, predates this branch.)

## 12. Measured state (branch-current, honest)

Retrieval 0.800@0.032 · rerank 0.665 max (STRUCK after 2 variants) · paths 0.072 diagnostic-only (teleport Δ+0) · T=2.58/ECE −86% (gate live, VERIFY 0.044) · transfer forced 0.327 (abstain 66%) · tev 0.094 STRUCK (phrasing-only) · v2 full-mix +0.039 @ matched-or-better clean-fire (KEEP, Task 3) · AC@1/flip/wall green on genuine probes · full suite blocked on Windows by pre-existing `fcntl` import (fails on main too — environmental, not a regression).

## 13. Struck / killed (do not revive without L1 reclassification)

MP-discord, learned-GDN, free-LLM narration, ROCm GPU, fixed thresholds, learned-graph detection, blind discovery, pretrained weights, live stream, Rust/Go core, Merlion-as-dependency, Jaeger backend, point-adjusted scoring, sensor dual-obs, dynamic/trajectory specialists, soft/weighted/vote-free rerank variants, hybrid +flow rows, full v2 general claim (pending full-mix).

## 14. Linear mapping (15 assigned: 4 closed by Task 1 docs, 11 open → plan tasks)

Done (Task 1): PRISSUE-65, 66-scope, 69, 70. In progress: PRISSUE-22 (CH8/CH9), PRISSUE-24 (duty-cycle) predate this batch. Open → plan: 75 oof+ranker-cal, 74 full-mix, 62 n=60, 63 ≤2 variants, 64 teleport, 72 recall+NLI, 61 gate wiring, 73 e2e script, 67/68 React panels, 71 two-stage phrasing, 66-E2E-number + 69 upkeep at ship. Full per-issue demands/evidence/next-actions: `SOLVE_GAPS.md` (worktree root).

## 15. Roadmap (future plan)

- **Now (Phase 0, ~1 day, zero code):** sign 66/65/70, write SHIP_STATUS (69). Unblocks everything's meaning.
- **Measure (Phase 1):** 75 rerun → 74 full-mix → 62 n=60 → 63/64 gated tries → 72 recall+NLI. Every kill bar enforced; wins and strikes both recorded.
- **Wire (Phase 2):** 61 gate → 73 script → 67/68 React panels → 71 phrasing (template default, LLM flagged + p95-gated).
- **Ship (Phase 3):** T12 + battery gates, 5× 0-diverge proof, held-out seed/rung confirmation of any tuned point, Linear updates with evidence, merge/PR decision.
- **Later (explicitly not now):** SGR bound promotion, ranker-level gate, cloud LLM (rejected: egress + cost), GPU (rejected: 1-wk driver box), live-stream semantics (waived), dual-obs (rejected pending plant justification), full v2 general claim (needs full-mix win first).

## 16. Open risks

Same-grid tuning cited as general (mitigation: held-out owed) · thin per-class coverage (8 eps/family) · 2-run vs 5× diverge proof · wall/p99/narration timing unevidenced · judge variance · small-model numeracy · exchangeability breaks under adaptive picks · fixture-vs-evidence confusion (battery.csv is CI-convention, not WS3 evidence).
