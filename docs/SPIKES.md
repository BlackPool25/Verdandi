# SPIKES — index (quarantine `spike/`, never merge; agent wall ≤30min each)

| Spike | Run | Vectors | Numbers | Verdict | Report |
|---|---|---|---|---|---|
| RQ1/RQ2 battery (real path) | `python spike/battery_rq1_rq2.py` | 50-coro · RSS 1k–10k · jitter probe · malformed 10/10 · 10× flat · mutation 0.824→0.058 | F1 0.734 (P .614/R .912) · AC@1 0.80 · lat3 0.65 · flip 14.4% · p99 3.7ms · wall 17.7s · MP F1 0.063 killed | K1 SURVIVE / K2 FIRES / CONDITIONAL | `REPORT_BATTERY.md` + `trace_battery.jsonl` |
| RQ3 narration | `python spike/rq3_spike.py` | 50-coro · RSS · 429/drops ≤8s · 5 hostile · 10× shed@500 · mutation 1.0→0.0 | grounded 1.00 · RSS 0.0% · 30/30 fallback 0.39s · 0 ungrounded/egress · caps $0.005/2.5k | FEASIBLE (template level) | `REPORT_RQ3.md` + `trace_rq3.jsonl` |
| RQ4/RQ5 replay+timing | `python spike/spike_rq4_rq5.py` | 50-coro · RSS 10k · jitter/drops · 10 malformed · 10× shed>6× · mutation | 0-diverge 5×5 · RSS +0.0% · flat-10× · fan-out-8 · Kingman-80% (LOWER BOUNDS, numpy surrogate) | FEASIBLE (harness) | `REPORT.md` + `traces/` |
| M0 echo (KILLED) | `python spike/m0_echo.py` | full 200ms probe · all six PASS | OFF 0.700→ON 0.726 (dP +.034, dR 0) · ceiling ≈0.76 · lat3 0.65→0.80 · wall 8.4s | KILL (works, insufficient) | `REPORT_M0.md` + `trace_m0.jsonl` |
| Close-out DELAY/LOSS+SimPy | `python spike/closeout.py` | V1/V2/V4/V6 PASS | DELAY F1 .670 5/6 flip 24.2% · LOSS F1 .739 5/6 flip 30.3% · 32f F1 .725 AC@1 .8125 p99 2.6ms · wall 3.1s · factorysimpy 0.1.0b3 unfit | K1 SURVIVE ×3 / KEEP-HANDROLLED | `REPORT_CLOSEOUT.md` + `trace_closeout.jsonl` |

Kill-gates (all spikes): RSS growth >5% → KILL · harness passing on corrupted code → vacuous-reject ·
10× OOM without shedding → KILL/PIVOT · happy-path-only → rejected. Libs: simpy 4.1.2 · stumpy 1.14.1 ·
tigramite 5.2.10.1 · networkx · numpy 2.4.6 (SeedSequence, zero bare default_rng) · psutil.
Context7 IDs: /stumpy-dev/stumpy · /jakobrunge/tigramite · /salesforce/merlion · /phamquiluan/rcaeval ·
/giampaolo/psutil · /python/cpython. Known caveats: battery V3 20ms scaled probe (M0 ran full 200ms);
OFF-baseline 0.734↔0.700 cross-run hash-seed jitter (within-run deltas valid); RQ4/RQ5 figures lower bounds.
