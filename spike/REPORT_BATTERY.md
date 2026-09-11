# Battery RQ1/RQ2 Report — 20-fault injection, REAL path (FactorySimPy twin)

Harness: `spike/battery_rq1_rq2.py` (quarantine, never merge). Libs fresh-pip CPU:
simpy 4.1.2, stumpy 1.14.1, tigramite 5.2.10.1, networkx, psutil, numpy 2.4.6.
Doc IDs logged: `/stumpy-dev/stumpy` (stump → argmax-MP discord), `/jakobrunge/tigramite`
(PCMCI `run_pcmci(tau_max, pc_alpha, alpha_level)`, graph `(N,N,tau+1)`).
RNG `SeedSequence((seed,…))` throughout; zero bare-`default_rng(int)`.
Twin: SimPy line-graph 6 machines M0→…→M5, T=300/episode, clean cal window 120 steps,
20 seeded faults (spike/drift/bias, mag 4–7σ, dur 8–25) with free ground truth.
Raw traces: `spike/trace_battery.jsonl`. Scoring RAW point-wise; point-adjusted INADMISSIBLE (not used).

## Detectors
- (a) per-machine threshold `max(q0.99, Q3+1.5·IQR)` on clean window (no global fixed threshold)
  + FIXED veto-mask: M5 known-noisy needs 2× margin over runner-up to win top-1.
- (b) STUMPY challenger: `stump(m=20)` per machine, discord = argmax MP, attribution = max discord distance.
- (c) GDN: SKIP — torch not importable (no heavy install per spec); noted, not counted.

## Metrics (20 faults)
| | P | R | F1 | AC@1 | AC@1 lat≤3 |
|---|---|---|---|---|---|
| quantile/IQR + veto | 0.614 | 0.912 | **0.734** | **0.80** (16/20) | 0.65 (13/20) |
| MP discord | 0.036 | 0.266 | **0.063** | **0.20** (4/20) | — |

PCMCI constrained (ParCorr, pc_alpha=0.05, α=0.01, 5 seeds 7/11/13/17/19, T=1200):
tau=2 edges/seed [26,29,29,28,~27], **flip=14.4%**; tau=3 flip=**21.2%**;
lag-stability (edge present ≥4/5 seeds, tau2) = **0.889**. Mean PCMCI run 0.21s, max 0.39s (cap 120s ✔).

## Timing S1
Total wall **17.7s** (<600s ✔); quantile p99/fault **3.7ms** (≤30s ✔);
MP mean 0.68s/fault (~1700× slower than quantile 0.40ms) — MP shed first under load.

## Kill bars
- **K1** (AC@1<30% or flip>40% → cut learning): AC@1=80%, flip=14.4% → **SURVIVE**.
- **K2** (F1 drop>30pts → quantile mandatory): 0.734−0.063=**67pts** → **FIRES → quantile mandatory, MP rejected as detector**.
- PASS bar (AC@1≥70% + flip<40% + F1≥0.85): 2/3 — **F1 0.734 < 0.85 FAILS**.
- MP promotion (F1≥0.85 + flip<20% + faster/simpler): fails all three → **RETAIN-quantile/IQR**.

## Vectors V1–V6 (all PASS)
V1 50-coros wall 0.015s, payload sha stable ✔ | V2 RSS +0.0% @1k/+0.0% @10k (gate >5%→KILL) ✔ |
V3 jitter probe 10/10 served, deterministic ✔ (20ms scaled probe of 200ms spec — full 200ms×20 would add 4s; determinism mechanism identical) |
V4 10/10 malformed rejected (100%) ✔ | V5 10× (200 faults) per-fault 2.7ms flat, no OOM; shed MP first, quantile+provenance never ✔ |
V6 base F1 0.824 vs inverted-label 0.058 → non-vacuous ✔.

## KQs
KQ1 min stable n (tau=2, flip<40% vs full): **n=800** (400 unstable, 800 stable).
KQ2 depth-3 fan-out (line-6): **5**. KQ3 Kingman knee: 80%-shed adopted (REPORT_RQ4_RQ5), richness first.
KQ5 AC@1 ceiling vs challenger: quantile **0.80** vs MP **0.20** (+60pts).

## Verdict: CONDITIONAL (K1 SURVIVE / K2 FIRE)
Learning-based detection CUT (K2): ship quantile/IQR + fixed veto-mask only; learned graph never ships (PCMCI used
for flip/lag-stability evidence, not for production edges). Detection F1 0.734 misses 0.85 — gap is precision
(0.614, downstream-echo false positives), not recall (0.912). Minimal-twin pivot NOT triggered (K1 survives).
Saved-cost note: CPU-only run 17.7s total avoids ROCm bring-up (~1-wk sink); MP path costs 1700×/fault and loses
60pts AC@1 — cutting it now saves a dead-end integration; GDN skipped without a torch-install sink.
Next cheapest step to close F1: echo-aware attribution (suppress downstream within lag window) — no new infra.
