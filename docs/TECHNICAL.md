# TECHNICAL — build reference (everything a builder needs, nothing more)

## Environment (pinned, CPU-only, no torch)
Python 3.14.7 · simpy==4.1.2 · stumpy==1.14.1 (offline-validation only — killed as detector) ·
tigramite==5.2.10.1 (evidence-only) · networkx==3.6.1 · numpy==2.4.6 · psutil==7.2.2 · scipy==1.18.1 ·
factorysimpy==0.1.0b3 installs but REJECTED (no trace/fault/RNG API → hand-rolled twin, ADR-0012).
`pip install simpy tigramite networkx numpy psutil` (+ stumpy for offline checks). No GPU, no ROCm.

## Config constants (single table — code MUST import these, never hardcode twice)
| Name | Value | Why | Gate |
|---|---|---|---|
| CAL_WIN | 120 steps | clean calibration | battery asserts |
| Q_DET | max(q0.99, Q3+1.5·IQR) per machine | K2: fixed thresholds killed | F1 raw |
| VETO_ASM2 | 2× margin over runner-up, ASM2-only (ex-VETO_M5, identical semantics) | ASM2 known-noisy tail | AC@1 |
| WALK_DEPTH / TOPK | ≤3 / top-k prune | exponential cap (fan-out cap 8 assembly join; line-scale fan-out-5 baseline only) | OOM gate |
| PCMCI | ParCorr, tau_max=2, pc_alpha=0.05, α=0.01 | flip 14.4%, lag-stab 0.889 | flip<40% |
| N_FLOOR | 800 | min stable n (KQ1) | flip<40% vs full |
| ECHO_W | 5 = tau2 + LAT_GATE(3) ≥ 5 hops | M0 (killed as closer, rule kept as doc) | — |
| NARR_DEADLINE | ≤8s → chain-cards | S2 (30/30 in 0.39s) | 100% served |
| CAPS | $0.005 / 2.5k tok / iter cap per run | $47K precedent | enforced |
| SHED_AT | queue util ≥80%, richness first | Kingman; 10× flat | never shed detection/provenance |
| SEED | SeedSequence everywhere, zero bare default_rng | 0-diverge 5×5 | K4 |

## Module map (spike → build; spike/ stays quarantine — rewrite, don't merge)
32-plant modules: `twin.py` (from battery_rq1_rq2.py: SimPy 32-machine plant Lines A/B/C 10/10/8 + ASM0–2 + RWK0 + AGV/SBUF, seeded faults) · `acquire.py` · `calibrate.py` (CAL_WIN=120) · `detect.py` (quantile/IQR per machine/channel) · `veto.py` (VETO_ASM2 fixed mask) · `walk.py` (depth≤3+top-k+fan-out cap 8) · `pcmci_job.py` (per-partition tau-2 evidence jobs) ·
`narrate.py` + `verify.py` (from rq3_spike.py: template, triple gate, caps) · `chaincards.py` (fallback) ·
`replay.py` (partition-scoped subgraph-only, pinned RNG) · `regress.py` (battery gates) · `trail.py` (SPEC export schema) · `ui/` (waterfall patterns).

## Fault taxonomy (seeded, free truth; 7 classes × 7 channels per SIM_SPEC §§5/8; measured numbers are line-scale baselines, bars unsoftened)
| Class | Params | Measured line-scale baseline (same detector) |
|---|---|---|
| spike/drift/bias (base, 20f) | mag 4–7σ, dur 8–25 | F1 0.734–0.739, AC@1 0.80, flip 14.4% |
| DELAY (6f) | lag-shifted propagation d≤tau window | F1 0.670, AC@1 5/6, flip 24.2% → mitigation: tau≥d window |
| LOSS (6f) | 10–30% observation drops | F1 0.739, AC@1 5/6, flip 30.3% → mitigation: better imputation |
| breakdown | forced DOWN window, MTTR×mult mult∈[1,3] | plant-scale re-measure at M0 exit, gate flip<40% per partition |
| quality (reject) | ASM2/RWK-path reject-rate 15–40% | plant-scale re-measure at M0 exit, gate flip<40% per partition |
32-fault totals line-scale baseline: F1 0.725, AC@1 0.8125, p99 2.6ms. Missed-fault sensitivity backlog: F-06/F-12/F-14 (M0b).

## Trace schemas (actual keys, single-record JSONL per run except rq3)
- `trace_battery.jsonl` (1 rec): twin, faults[], quantile{}, mp{}, gdn, pcmci{}, pcmci_timing_s,
  lag_stability_tau2_ge4of5, per_fault[], timing{}, S1{}, PASS_bar{}, K1{}, K2{}, KQ*{}, overall{}, vectors{}, wall_total_s.
- `trace_m0.jsonl` (1 rec): ablation{off,on,delta}, echo_W(+basis), n_floor checks, per_fault[], vectors{}, PASS_bar{}.
- `trace_closeout.jsonl` (1 rec): fault_counts, per_class{}, totals{}, factorysimpy{}, K1_global{}, S1{}, vectors{}.
- `trace_rq3.jsonl` (37 recs): vector, n, grounded, sentences[].
- `traces/`: timing.json (total_s, per_fault_p99_s, gates, worst_fanout) + v0–v6 vector files.

## Fallback matrix (failure → behavior → gate)
Model tail/429/drop → chain-cards ≤8s (K3) · >5% ungrounded → fallback stays (K3) · diverge → subgraph-only
(K4) · ROCm sink → CPU default (K5) · flip>40%/AC@1<30% → cut learning, topology+stats (K1) ·
F1-drop>30pts → quantile mandatory (K2) · 10× surge → shed richness first (never provenance) ·
RSS>5% → KILL · harness-green-on-corrupt → vacuous-reject.

## Regression procedure (every milestone ends here)
`python spike/battery_rq1_rq2.py && python spike/closeout.py` → PASS iff F1≥0.85(M0b target; disclose
until then) + AC@1≥70% + flip<40% per partition per class + p99≤30s + total<600s + vectors green. Log JSONL as run id.
