# Close-out Report — DELAY/LOSS robustness + FactorySimPy fit (two loose ends)

Harness: `spike/closeout.py` (quarantine, never merge). Libs: simpy 4.1.2, tigramite 5.2.10.1,
numpy, psutil + `factorysimpy==0.1.0b3` (PyPI, MIT, requires simpy>=4.1.1; context7 IDs:
`/stumpy-dev/stumpy`, `/jakobrunge/tigramite` inherited from battery; pip index used for
package resolution, ID logged here). Detector UNCHANGED: per-machine `max(q0.99, Q3+1.5·IQR)`
+ fixed veto-mask (no new architectures). Raw: `spike/trace_closeout.jsonl` (+ per-fault rows).
Wall **3.1s** (<600s ✔, ≤30min ✔). Scoring raw point-wise; point-adjusted inadmissible (unused).

## (a) DELAY + LOSS battery (seeded, free GT; 6 faults each)

- DELAY (rng 777): spike at origin, downstream echo lag-shifted by extra d∈[3,6] steps.
- LOSS (rng 999): spike/bias at origin + 10–30% random observation drops post-calibration,
  naive clean-median imputation baseline before detection (cal window intact).

| class | n | P | R | F1 | AC@1 | AC@1 lat≤3 | PCMCI tau2 flip | edges/seed | K1 class-gate |
|---|---|---|---|---|---|---|---|---|---|
| base | 20 | 0.602 | 0.956 | 0.739 | 0.80 | 0.65 | 14.4% | [29,26,29,29,28] | SURVIVE |
| delay | 6 | 0.503 | 1.000 | 0.670 | 0.83 (5/6) | 0.83 | 24.2% | [9,13,9,10,12] | SURVIVE |
| loss | 6 | 0.622 | 0.910 | 0.739 | 0.83 (5/6) | 0.83 | 30.3% | [21,23,23,22,22] | SURVIVE |

Base reproduces battery within run-jitter (F1 0.739 vs 0.734, AC@1 0.80 = 0.80, flip 14.4% =
14.4%; ±1pt F1 jitter is per-process string-hash seeding in `SeedSequence((seed, hash(id)))`,
AC@1/flip stable — noted, not a gate issue).

Class notes (mitigation, no global pivot — K1 global SURVIVE, no class fired):
- DELAY: precision dips (0.503, echo window stretched by d) but recall 1.00, AC@1 5/6.
  Flip 24.2% <40% but elevated vs base; long-trace truth at lag-4 with tau_max=2 is
  misspecified by construction (fewer stable edges: ~11 vs ~28). Class mitigation if d grows:
  widen PCMCI window to tau≥d for evidence only — detector itself needs no change (origin
  peak unaffected by downstream shift).
- LOSS: F1 0.739 = base level under naive median imputation; flip 30.3% <40% but closest
  to the gate (imputation noise thins stable edges: ~22 vs ~28). Class mitigation if drop
  rate exceeds 30%: forward-fill/Kalman imputation + widen cal window — again evidence-side
  only. RCAEval blind-spot precedent (BARO dies on DELAY/LOSS) does NOT reproduce here:
  quantile/IQR degrades gracefully, attribution holds.

Totals re-assert (32 faults): F1 **0.725**, AC@1 **0.8125** (26/32, ≥70% ✔),
AC@1-lat3 0.719, q-p99 **2.6ms** (≤30s ✔), total 3.1s (<600s ✔).
Vectors: V1 50-coros 0.015s PASS | V2 RSS +0.0%/+0.0% PASS | V4 10/10 reject PASS |
V6 0.792→0.071 non-vacuous PASS. Per-PCMCI max <120s cap ✔ (slowest ~0.4s).

## (b) FactorySimPy fit — verdict: KEEP-HANDROLLED (pin `factorysimpy==0.1.0b3` as evaluated)

- Install: `pip install factorysimpy==0.1.0b3` OK (wheel 104kB, +0 deps beyond simpy).
- 3-machine line (Source→M0→Buf→M1→Buf→M2→Sink) builds and runs to t=200 in 0.01s
  (sink=63, machined=[65,64,63]); constant-delay rebuild reproduces exactly (deterministic ✔
  in the trivial sense).
- Fit gaps (each fails a USE-PACKAGE condition — needs strictly-less-glue AND seeded AND
  deterministic): (1) discrete-only item flow, BOM/static-oriented — observations are
  counts-only stats (`num_item_processed/discarded`, time-in-state), NO continuous
  per-machine signal trace, so the entire signal/fault layer must still be hand-built on top
  (≥ same ~29-line wiring PLUS missing layer → strictly MORE glue, not less);
  (2) no seeded-fault support — no inject/fault/degrade parameter in Machine/Source/Buffer
  signatures; (3) no determinism hooks — no SeedSequence/RNG parameter (`RANDOM`
  edge-selection exists unseeded); determinism holds only via constant delays (fragile).
  Side: no quiet flag — nodes print per-event stdout (log spam at scale).

## Verdict: both ends CLOSED with numbers

K1 global SURVIVE (no class <30% AC@1, no class >40% flip). Project stays CONDITIONAL
(F1 0.725 < 0.85 bar — precision, not recall: R 0.957). No scope taken beyond the two ends;
MP/GDN stay rejected/killed; no learned-graph shipping; no gate softening.
Saved-cost note: 3.1s CPU run closes the RCAEval-blind-spot question empirically, and the
package probe (0.01s build + signature audit) kills a migration that would have added a
dependency AND a signal-layer rewrite for zero twin gain — hand-rolled SimPy twin retained,
SemVer pin recorded above.
