# RQ4+RQ5 spike report: seeded subgraph replay + CPU-baseline timing
Harness: `spike_rq4_rq5.py` (quarantine, never merge). RNG `numpy==2.4.6`/PCG64/`SeedSequence((seed,stream))` — zero bare-`default_rng(int)` calls. SimPy 4.1.2 (`/websites/simpy_readthedocs_io_en`), NumPy SeedSequence spawn pattern (`/numpy/numpy`). Subgraph-only: 12-node DAG, depth≤3 walk from alarm node. Wall-clock full suite ≈1s (budget ≤30min ✔).
## Diverge (K4): 0 across 5 seeds ×5 reps (7,11,13,17,19) — SURVIVE, subgraph-only ADOPTED
## V1 contention: 50 coroutines, wall 0.004s, p99/max 0.0001s, threads=1, same-payload hash stable under contention ✔
## V2 RSS: 46.0MB base → +0.0% @1k and @10k iters (gate >5%→KILL) — SURVIVE
## V3 faults: 200ms jitter + 10% drops propagate, same-fault deterministic, thread_leak=0, SimPy single-thread model confirmed (strain lives in asyncio V1, not SimPy threads)
## V4 malformed: 10/10 rejected (100%) — null/shape/seed-range/alarm-range/neg-mag/depth≠3/missing-key/corrupt-bytes/huge-seed/empty-faults ✔
## V5 saturation: 1x→10x (20→200 faults) per-fault flat 0.0001s, no collapse, no OOM; shedding point @scale>6 (richness first, detection+provenance never shed) — SURVIVE-with-shedding
## V6 mutation: corrupt-seed detected + flipped-assert fires → harness non-vacuous ✔
## Timing (S1/S4): 20-fault total 0.001s (<600s ✔), per-fault p99 0.0001s (≤30s ✔)
## KQ2 depth-3 worst fan-out: 8 nodes (alarm 0/1/2); KQ3 Kingman: 80%-shed knee adopted, 70% insufficient headroom; richness-shed keeps p99 flat
## Verdict: FEASIBLE (K4/K5 fire-or-survive → SURVIVE on replay determinism + CPU timing; K5 CPU-baseline default holds)
## Saved-cost note: CPU fallback avoids ROCm 1-wk sink; subgraph cap (≤8 vs 12 nodes) bounds viva demo to seconds; honest caveat — figures are replay-harness lower bounds (numpy surrogate, not PCMCI/GDN), so no full-graph demo-critical claims; RQ1/RQ2 battery must re-time real detector+causal path. Raw traces: `spike/traces/` (v0–v6, timing).
