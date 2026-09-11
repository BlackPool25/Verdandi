# TEST_CASES — anomaly-twin-trace (ATT-TP-001 companion)

Source of truth for gates: `docs/TEST_PLAN.md`. Kill bars: K1 AC@1<30% or flip>40% → cut learning, keep topology+stats. K2 F1 drop>30pts vs quantile → per-machine quantile mandatory, global thresholds excluded. K3 >5% ungrounded → cut LLM to chain-cards. K4 any diverge → subgraph-only replay. K5 ROCm sink >1wk → CPU-baseline. No gate softening. `spike/` is quarantine, rewrite-don't-merge.

Global pass conjunct (every TC that asserts release): F1≥0.85 AND AC@1≥70% (intra-partition AND cross-partition via gateway buffers) AND flip<40% per partition per class incl. breakdown/quality AND p99 detection delay ≤3 steps AND wall <600s via partitioning AND grounding ≥95% AND 0-diverge AND full-plant coverage (all partitions × channels × classes, no empty cell). Any conjunct fails or any sev-1 open → K-pivot fires. Plant-scale note: line-scale battery numbers (17.7s, flip 14.4–30.3%, fan-out-5) are carried as baselines; walk fan-out and wall time are re-measured at plant scale as M0 exit measurements — no invented plant numbers in this file. K-gates K1/K2 evaluate per partition (only failing partition falls back); K3/K4/K5 stay plant-wide. M0b runs under frozen pre-registration `docs/M0B_PREREG.md` (fault list, fixed-percentile calibration, PA-off primary + PA-on control, no-subsetting rule) — no battery runs outside the prereg.

Conventions: commands run from repo root. Fault IDs F-01..F-20 = 20-fault battery set (`spike/trace_battery.jsonl`); F-21..F-26 = DELAY class (seed 777); F-27..F-32 = LOSS class (seed 999); total 32-fault set = `spike/trace_closeout.jsonl`. Plant scale: 32 machines per SIM_SPEC (Lines A/B/C 10/10/8 + ASM0–2 + RWK0, AGV pool + shared overflow buffer, mass-flow-conserved); PCMCI runs one evidence job per partition (never full-plant graph — banned: O(N²×tau) at N=32 breaks CPU bar). PCMCI seeds always {7,11,13,17,19}, ParCorr pc_alpha=0.05, alpha_level=0.01, tau_max=2 (tau=3 evidence-only in PCMCI jobs, never production/walk). Detector frozen: per-machine `max(q0.99, Q3+1.5·IQR)` on clean cal window 120 + fixed veto-mask VETO_ASM2 only (ex-VETO_M5, identical 2x-margin semantics; ASM2-test needs 2x margin over runner-up, no other mask). Scoring raw point-wise only, point-adjusted inadmissible. Walk: depth≤3 intra-partition + 1 gateway hop exempt from depth cross-partition; fan-out cap 8 for the assembly join per SIM_SPEC §7.3 (line-scale fan-out-5 carried as baseline only, plant fan-out re-measured at M0 exit). Name disambiguation: ECHO_W=5 (echo suppression window) vs GAP_MIN=5 (min inter-window gap same machine per SIM_SPEC §4.3).

## TC-001 — TST-001 battery-F1-full-flow (M0b gate, only open bar)

- TST: TST-001 (REQ-001/010).
- Preconditions: CPU laptop, `simpy==4.1.2 stumpy==1.14.1 tigramite==5.2.10.1 networkx numpy==2.4.6 psutil` installed; taus frozen; `spike/battery_rq1_rq2.py` unmodified.
- Test data: 20 faults F-01..F-20, T=300/episode, cal-win 120, classes spike/drift/bias mag 4-7σ dur 8-25, twin line M0→M5. Known-missed subset F-06/F-12/F-14 (recall 0) must be present.
- Steps:
  1. `python spike/battery_rq1_rq2.py` (expect wall ≈17.7s).
  2. Read `spike/trace_battery.jsonl` per-fault rows; compute raw point-wise P/R/F1.
  3. Confirm missed set is subset of {F-06, F-12, F-14} and no recall regression on those three vs prior run.
  4. Confirm F1 uses raw scoring (grep report for point-adjusted = unused).
- Expected: raw F1≥0.85 (baseline observed 0.734 FAIL, M0b must close via echo-aware attribution); recall on F-06/F-12/F-14 strictly improved, zero regressions on other 17.

## TC-002 — TST-001 sensitivity drill-down (M0b first step)

- TST: TST-001 (REQ-001).
- Preconditions: TC-001 artifacts present.
- Test data: F-06, F-12, F-14 isolated.
- Steps:
  1. Re-run battery with per-fault dump (`python spike/battery_rq1_rq2.py --dump-per-fault` or inspect per_fault[] in JSONL).
  2. For each of F-06/F-12/F-14 record detector score vs threshold, veto-mask decision, downstream-echo window overlap.
  3. Classify cause: threshold-shape vs feature vs cal-window vs echo-attribution.
  4. Apply one targeted fix only (echo-aware attribution preferred per REPORT_BATTERY), re-run full 20-fault battery.
- Expected: fix attribution documented; F-06/F-12/F-14 recall >0; full-set F1≥0.85; no other fault flips from TP to FN.

## TC-002b — PA-on control arm (protocol neutrality, per M0B_PREREG.md §3)

- TST: TST-001 (REQ-001).
- Preconditions: TC-001 artifacts present.
- Steps:
  1. Score the identical battery PA-on alongside the PA-off primary.
  2. Compare detector ranking and top-gap under both protocols.
- Expected: PA-on flips the detector ranking OR compresses the top-gap by ≥0.30 (protocol-neutrality demonstrated on our own data). Else protocol-neutrality fails — results are not reported as PA-robust, and the primary claim stays PA-off-only.

## TC-003 — TST-002 causal accuracy (partitioned PCMCI, 5 seeds)

- TST: TST-002 (REQ-001).
- Preconditions: battery trace from TC-001.
- Test data: 20 faults, PCMCI seeds 7/11/13/17/19, T=1200 window, tau_max=2, n≥800 floor per partition; cross-partition fault subset (origin and symptom in different partitions, path via gateway buffer) ≥20% of battery at plant scale.
- Steps:
  1. `python spike/battery_rq1_rq2.py` (PCMCI block runs 5 seeds internally; at plant scale run one job per partition).
  2. Extract edges/seed per partition (line-scale baseline [26,29,29,28,~27]), flip rate per partition, lag-stability (edge present ≥4/5 seeds).
  3. Compute AC@1 = top-1 ranked cause == injected machine over 20 faults, split into intra-partition AC@1 and cross-partition AC@1 (gateway-hop path).
- Expected: AC@1≥70% intra AND cross-partition (observed line-scale 0.80, closeout 32-fault 0.8125 — carried as baseline, re-measured at plant scale); flip<40% per partition (observed line-scale tau2 14.4%); lag-stability ≈0.889 per partition; per-partition PCMCI run <120s cap (observed line-scale mean 0.21s, max 0.39s). K1 evaluates per partition.

## TC-003a — masked-vs-blind PCMCI+ (same battery, mask-signal check)

- TST: TST-002 (REQ-001). Preconditions: TC-001 battery traces, seed hashes logged.
- Test data: same fault battery, both arms, ≥5 seeds, n≥800 per arm.
- Steps:
  1. Masked arm (topology prior on) vs blind arm (no prior) on identical seeds.
  2. Record flip rate per arm per partition.
- Expected: masked flip ≤14.4% AND blind gap ≥10pp (masked minus blind). Kill-tripwire: masked >14.4% or blind within ±5pp → mask carries no signal; demote mask-dependent reading (blind suffices at this scale).

## TC-003b — 10% mask-corruption arm (prior-sensitivity)

- TST: TST-002. Preconditions: TC-003a artifacts.
- Steps: randomly corrupt 10% of mask entries, re-run masked arm on same seeds.
- Expected: flip degrades ≥3pp vs clean mask (mask carries signal). Else mask demoted — result does not depend on mask quality (prior-fragility wins).

## TC-004 — TST-003b stability per class per partition (flip gate)

- TST: TST-003b (REQ-006 flip).
- Preconditions: as TC-003.
- Test data: base 20 (seeds per battery) + DELAY 6 faults seed 777 (d in [3,6]) + LOSS 6 faults seed 999 (10-30% drops, median imputation); at plant scale each partition carries its own class subset.
- Steps:
  1. `python spike/battery_rq1_rq2.py` → record base flip per partition.
  2. `python spike/closeout.py` (expect line-scale wall ≈3.1s) → record DELAY flip, LOSS flip, edges/seed per partition.
  3. Assert each class flip<40% independently in every partition (partition-level gate, not plant-averaged).
- Expected: line-scale baselines base 14.4%, DELAY 24.2%, LOSS 30.3% (all <40%, K1 SURVIVE per class per partition). If any partition × class >40% → K1 partition-pivot: widen PCMCI window to tau≥d evidence-only in that partition, detector unchanged elsewhere.

## TC-004a — graph-free ablation (BARO-style) + DELAY/LOSS miss-tagging

- TST: TST-002/TST-003b. Preconditions: TC-003/TC-004 artifacts, same battery and seeds.
- Steps:
  1. BARO-style graph-free ranking arm (no causal graph, no topology prior) on the full battery; record AC@1.
  2. Tag every miss per M0B_PREREG.md §6 (DELAY / LOSS / GATEWAY / NOVEL).
  3. Compute DELAY:LOSS miss-rate ratio.
- Expected: AC@1≥0.70 AND graph-vs-graphfree gap ≥10pp (topology prior earns its keep). Gap <10pp → concede BARO parity for this twin. Ratio ≥2:1 confirms the RCAEval-hard reading; uniform misses (±10pp) force the unambitious-battery reading (faults too easy — re-seed harder).

## TC-005 — TST-004 latency p99 ≤3 steps

- TST: TST-004 (REQ latency).
- Preconditions: TC-001 trace.
- Test data: same 20 faults + 12 DELAY/LOSS faults.
- Steps:
  1. From `trace_battery.jsonl` per-fault rows compute detection delay steps (first alarm t - fault t_start).
  2. From `trace_closeout.jsonl` repeat for F-21..F-32.
  3. Compute p99 over 32 faults; also AC@1-lat3 fraction.
- Expected: p99 ≤3 steps; AC@1-lat3 reported (observed base 0.65, closeout totals 0.719, DELAY/LOSS 0.83 each). Wall-clock p99/fault ≤30s (observed 3.7ms battery, 2.6ms closeout).

## TC-005-ext — H4 RAG-control audit (template+verifier vs open+RAG, n≥50 alarms)

- TST: TST-005 (REQ-002) on the TST-004 alarm set.
- Preconditions: M2 narration wiring built (template+verifier+chain-cards; NLI critic deberta-v3 inside verifier per ADR-0013, NLI-critic-only). Open+RAG arm = same model with retrieval over the same traces but no template, no verifier, no fallback.
- Test data: SAME alarm set for both arms, n≥50: all 32 plant-battery fault alarms + ≥18 RQ3 hostile/coroutine alarms (5 adversarial prompts + 429/drop injections). Neither arm sees a different set.
- Steps:
  1. Run template+verifier arm on all n alarms; log per sentence: text, provenance triple (fault-window, edge-id, detector-output) or fallback flag, verifier accept/reject.
  2. Run open+RAG arm on the identical n alarms; apply the same per-sentence provenance-ID check (triple resolves or the sentence is an escape).
  3. Classify every non-fallback sentence without a resolving triple into the escape taxonomy: (i) forced-hallucination-to-satisfy-grammar (fluent filler invented to complete a template/grammar slot), (ii) invented edge-id, (iii) wrong fault-window, (iv) detector-output mismatch, (v) unverifiable entity. Fallback-flagged sentences are not escapes; they count toward the fallback-fire rate.
  4. Log fallback-fire rate (fallback sentences / total sentences) per arm to `alarm-audit.csv` (columns: alarm_id, arm, sentence_id, triple_ok, escape_class, fallback).
- Expected (close-out): template+verifier arm ≥95% sentences with resolving triple (relax to ≥90% only with wiring-time measurement evidence recorded in the trail); AND zero non-fallback escapes in the template arm. Open+RAG arm reported as-is as the control.
- Kill-tripwires (fire on measurement, no re-interpretation): template arm <90% → drop the template-superiority claim, ship fallback-only per K3; open+RAG arm ≥80% grounded → drop the verifier-necessity claim, verifier becomes optional hardening; verifier rejects constantly (fallback-fire rate ≈100%) → report the system as effectively-fallback-only, no template victory claimed.

## TC-006 — TST-003 full-plant coverage (partitions × channels × classes)

- TST: TST-003 (REQ-010).
- Preconditions: battery + closeout traces.
- Test data: coverage matrix rows = partitions (Line-A/B/C, assembly cell, rework loop) × machines, columns = channels (vibration/thermal/throughput/quality/state/buffer/event per SIM_SPEC §8) × classes (spike/drift/bias/delay/loss/breakdown/quality per SIM_SPEC §5). Minimum 1 injected fault per partition × class, and every machine × every injectable class ≥1 across the plant battery (representative-machine subset per SIM_SPEC §5 mandatory, full cross product target); every fault carries whole-plant replay context (full partition traces + gateway buffers, not subgraph-clipped at inject time). Line-scale 6/6-machine matrix carried as baseline subset.
- Steps:
  1. `python spike/battery_rq1_rq2.py && python spike/closeout.py` (plant battery extends the same commands per partition).
  2. Build matrix from `trace_battery.jsonl` + `trace_closeout.jsonl` (fault origin partition/machine × channel × class), plus cross-partition column (faults whose symptom surfaces in a different partition via gateway).
  3. Assert all partitions present, all 7 channels × 7 classes present per partition group; flag any empty cell.
  4. Spot-check one alarm per partition plus one cross-partition alarm: replay context contains origin-partition window + gateway buffer window + symptom-partition echo.
- Expected: full-plant coverage, zero empty cells (line-scale 6/6 machines, 5/5 classes was the prior bar — now a subset of 7×7). Empty cell → add seeded fault to that cell and re-run (never ship with a gap).

## TC-006b — TST-003/TST-008 flow-semantics (AGV/SBUF/rework/states)

- TST: TST-003 (REQ-010) + TST-008 (REQ-007 shed).
- Preconditions: plant episode dicts `{obs[32][300], states[32][300], buffers[31][300], agv_waits, parts, faults}` present.
- Test data: tail-to-ASM0 transfers under AGV cap-2 contention; SBUF-divert episodes; ASM2→RWK0→ASM0 rework route; BLOCKED/STARVED/DOWN windows.
- Steps:
  1. AGV-wait bound: every tail→ASM0 transfer holds one AGV for agv_steps∈[4,8]; `agv_waits[]` logged, queue bounded, no transfer without a hold.
  2. Rework max-passes cap: rejected parts route ASM2→RWK0→ASM0 and re-enter kitting; assert pass count capped, no infinite rework loop.
  3. SBUF-overflow: tail-full divert allowed only for process/finish classes (feed/form never); SBUF occupancy logged, drains to ASM0 on free AGV.
  4. State asserts: BLOCKED iff downstream full (holds part, emits 0 throughput); STARVED iff upstream empty (ASM0: any kit input empty); DOWN preempts BLOCKED/STARVED; natural-breakdown steps flagged, excluded from fault ground-truth windows.
  5. 10x surge probe: shed richness first, detection/provenance intact, walk result still served.
- Expected: all four asserts hold per episode; surge sheds rich sentences only. Fail → block release, file sev-1 against twin.

## TC-007 — TST-005 grounding ≥95% (sentence provenance audit)

- TST: TST-005 (REQ-002).
- Preconditions: narration wiring (template+verifier+chain-cards) built per M2.
- Test data: 20 battery alarms; RQ3 hostile set: 5 adversarial prompts + 429/drop injection + ≤8s deadline; caps $0.005 / 2.5k tokens / iter.
- Steps:
  1. `python spike/rq3_spike.py` → check `spike/trace_rq3.jsonl`.
  2. For each explanation sentence assert triple ≡ (fault-window, edge-id, detector-output) resolves; verifier rejects null/unresolvable.
  3. Force deadline breach (kill model mid-call) → confirm chain-card fallback serves 30/30 in ≤8s.
  4. Compute grounding rate = sentences with valid triple / total.
- Expected: ≥95% (observed 1.00, 0 ungrounded/egress, 30/30 fallback in 0.39s). <95% → K3 fires: LLM cut, chain-cards only. Caps ledger audited per run ($0.005/2.5k tok/iter; breach aborts rich first).

## TC-008 — TST-006 determinism 5×5 same-seed 0-diverge

- TST: TST-006 (REQ-003).
- Preconditions: replay module subgraph-only, SeedSequence everywhere, zero bare `default_rng(int)`.
- Test data: 5 representative faults (one per class incl. F-06), 5 seeds each → 25 replays.
- Steps:
  1. `python spike/spike_rq4_rq5.py` (replay block) or `python spike/spike_rq4_rq5.py --replay-only`.
  2. Hash each replay output (subgraph + ranked cause + explanation); diff across same-seed runs.
  3. Confirm whole-flow context preserved despite subgraph-only execution.
- Expected: 0-diverge byte-identical across all 25 (observed 5×5 PASS). Any diverge → K4: subgraph-only enforced, full-graph stochastic path removed.

## TC-009 — TST-007 perf <600s CPU E2E via partitioning

- TST: TST-007 (REQ-006).
- Preconditions: one CPU laptop, no GPU, no torch.
- Test data: 20-fault battery + 12-fault closeout + 50-coro contention probe + 10x flat-load (200 faults).
- Steps:
  1. `time python spike/battery_rq1_rq2.py` → assert wall <600s (observed line-scale 17.7s — baseline; plant-scale re-measured at M0 exit, must hold via per-partition jobs, no invented number here).
  2. `time python spike/closeout.py` → assert wall <600s (observed line-scale 3.1s — baseline).
  3. Check V1 50-coros wall ≈0.015s; V2 RSS growth ≤5% at 1k/10k; V5 10x per-fault flat ≈2.7ms no OOM; V4 10/10 malformed rejected; V6 inverted-label F1 collapses (0.824→0.058 battery, 0.792→0.071 closeout, non-vacuous). At plant scale V5 runs per partition; full-plant PCMCI is not run (banned).
  4. Assert-no-torch gate: `python -c "import torch"` must fail (torch not importable); grep build for torch/GPU imports = 0 hits.
- Expected: total E2E <600s via partitioning; p99/fault ≤30s; RSS +0.0%; 10/10 malformed rejected; mutation gap proves non-vacuous. K5 timebox: ROCm/GPU bring-up timeboxed to 1wk max, on expiry → K5 fires: stay CPU-baseline, do not attempt GPU in test window.

## TC-010 — DELAY/LOSS per-class regression gates (M1, per partition)

- TST: TST-001 + TST-002 + TST-004 per class (REQ-001/006).
- Preconditions: TC-004 artifacts.
- Test data: DELAY seed 777 (6 faults), LOSS seed 999 (6 faults); gates evaluated per partition at plant scale.
- Steps:
  1. `python spike/closeout.py`.
  2. Per class per partition compute P/R/F1, AC@1, AC@1-lat3, flip.
- Expected: line-scale baselines DELAY F1≈0.670 R=1.00 AC@1 5/6 lat3 0.83 flip 24.2%; LOSS F1≈0.739 AC@1 5/6 lat3 0.83 flip 30.3%; 32-fault totals F1≈0.725 AC@1 0.8125. Mitigations armed (not applied unless worsened): DELAY tau≥d evidence window in failing partition; LOSS forward-fill/Kalman + wider cal if drop rate >30%.

## TC-010b — breakdown/quality per-class gates (per partition)

- TST: TST-001 + TST-002 + TST-004 per class (REQ-001/006).
- Preconditions: TC-004/TC-010 artifacts; episode dicts carry states + rework/SBUF logs.
- Test data: BREAKDOWN origins A7, B2, C6, ASM1 (forced DOWN, MTTR×mult mult∈[1,3], dur 8–25); QUALITY origins ASM2, RWK0, A9, B9 (reject-rate 15–40%, dur 8–25); gates evaluated per partition.
- Steps:
  1. Run plant battery covering both classes ≥1 per representative machine.
  2. Per class per partition compute P/R/F1, AC@1, AC@1-lat3, flip.
  3. Confirm observables: breakdown → BLOCKED upstream + STARVED downstream, origin throughput zero; quality → rework-buffer surge + ASM0 kitting starve + sink throughput dip.
- Expected: flip<40% per partition per new class (K1 partition-pivot on breach, bars unsoftened); F1/AC@1/lat3 reported per class per partition and pooled into the global conjunct (F1≥0.85 pooled, AC@1≥70% intra+cross). Natural-breakdown steps excluded from ground-truth windows.

## TC-011 — Full-flow viva demo E2E (release gate, all TSTs)

- TST: TST-001 through TST-010 combined (REQ-001..010, zero orphans).
- Preconditions: M0b→M4 complete; waterfall UI + trail export wired.
- Test data: 20-fault battery (F-01..F-20 incl. F-06/F-12/F-14) + 1 DELAY + 1 LOSS spot fault + 1 cross-partition spot fault (origin ≠ symptom partition); examiner picks any alarm live.
- Steps:
  1. `python spike/battery_rq1_rq2.py` (or built `twin.py` full-plant run) → detect → veto → walk (intra + gateway cross-partition) → narrate+verify → replay → UI + trail export.
  2. Examiner clicks one alarm in waterfall: check rank cause + sentences+triples + replay hash displayed.
  3. Re-run same seed live → show byte-identical replay hash (0-diverge).
  4. Read out all eight numbers: F1, AC@1 (intra + cross-partition), flip per partition per class, p99 delay, wall time, grounding, diverge count, full-plant coverage.
  5. No-clearance audit (TST-010/REQ-009): grep twin/UI/trail text for clearance/restart-authority strings = 0 hits.
- Expected: F1≥0.85 AND AC@1≥70% intra AND cross-partition AND flip<40% per partition per class AND p99≤3 steps AND wall<600s via partitioning AND grounding≥95% AND 0-diverge AND full-plant coverage (partitions × channels × classes), examiner-clickable, trail exported per alarm (rank + sentences+triples + replay hash + battery numbers). Any miss → release blocked, mapped K-pivot fires (K1/K2 per partition, K3/K4/K5 plant-wide).
