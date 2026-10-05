# M0.2f Fallback Audit — Independent Mathematical/Statistical Review

**Issue:** PRISSUE-29 (M0.2f multi-scale window export, assignee: gowtham) · **Project:** Verdandi (`/home/shreyas/projects/Verdandi`)
**Normative specs:** `upgrade-spec.md §5` + `training-preprocessing-spec §3.4` · **Twin truth:** T=300, CAL_WIN=120, WARMUP=15, 26 machines (`src/config.py`)
**Stated M0.2f N:** 105 (discrepancy flagged — do NOT hardcode 105 without resolving vs T=300)
**Status:** No `src/window_export.py` exists yet.
**Claim-strength labels:** [THEOREM/PROOF] · [ESTABLISHED STATISTICAL RESULT] · [PRIMARY-SOURCE EMPIRICAL METHOD] · [ENGINEERING ADAPTATION] · [HEURISTIC] · [NOT DEFENSIBLE]

---

## 1. FINAL VERDICT

**NO mathematically justified universal point-fallback B = f(N) exists under the current specification.** [THEOREM/PROOF for the negative result, given the anomaly model in §2.]

What *is* defensible:

1. **No point fallback. Emit `B_i=null, scale_status=unresolved` + a neutral, exactly-reconstructible covering representation, and defer scale selection downstream.** This makes no physical/statistical claim it cannot support.
2. Concretely: for unresolved channels, export **prefix sums (S, Q) + a range-min/max structure** as the canonical sufficient representation — or, if the rolling-row schema must be preserved, the dyadic rolling bank **{1,2,4,8,16,32,64} as an [ENGINEERING ADAPTATION] with a [THEOREM/PROOF] of exact reconstructibility for 4 of 5 features**, never as an optimality claim.
3. In parallel, **pool B_i estimation across training episodes only** (leakage-disciplined). This is the only legitimate way to "solve" small-N — it increases effective sample size M×N rather than inventing f(N). If pooling still yields no validated B_i, the channel stays `unresolved`. That is a result, not a failure.

## 2. NON-UNIVERSALITY PROOF (Q1 — no universal f(N))

**Claim:** no function B = f(N) using only N can be uniformly optimal over the anomaly types M0.2f must detect. [THEOREM/PROOF, conditional on the standard matched-filter/SNR model.]

Setup: white noise N(0,σ²), windowed-mean detector over window length w, stride-1, no padding.

- Case A — sustained anomaly length L, amplitude A: matched window w=L gives standardized mean ≈ A√L/σ, increasing in L. Signal sum = AL, noise std = σ√L, ratio = AL/(σ√L). [ESTABLISHED STATISTICAL RESULT — matched filter optimality via Cauchy–Schwarz.]
- Case B — 1-sample pulse amplitude A: window w dilutes it: ≈ A/(σ√w), maximized at w=1.

Hence argmax_w SNR depends on L (unknown signal duration), not N. Any fixed f(N) is simultaneously wrong for L=1 and L≫1. This is the **known-signal requirement of the matched-filter theorem** and a **Neyman–Pearson** point: the most powerful test needs the likelihood ratio, i.e. the signal model.

Structural reasons f(N) fails here: heterogeneous channels (periodic vibration vs event/state/buffer/energy); fault durations 8–25 (`FAULT_RANGES`), drift ramps, delay d∈[3,6], wear-knee drift — L varies by class; N=105 is not even the twin's T (300).

**Any N-only triple ([8,16,32], [13,26,53], [11,22,44], N^(2/3)): [NOT DEFENSIBLE] as stated, [HEURISTIC] at best if relabeled with a sensitivity report.**

## 3. AUDIT OF ALL PROPOSALS

| Proposal | Verdict |
|---|---|
| TAVILY N^(2/3)→[11,22,44] | [NOT DEFENSIBLE]/[HEURISTIC]. n^(2/3) rates come from histogram/bin/block-bootstrap/bandwidth problems with different losses. No link to mean/RMS/min/max/envelope on industrial signals. Prefactor data-dependent. |
| PERPLEXITY [13,26,53] = N/8,N/4,N/2 | [NOT DEFENSIBLE]/[ENGINEERING ADAPTATION] if relabeled. No finite-sample theorem. w=53 leaves 53 stride-1 positions — a cost, not a proof. |
| EXA R1 [8,16,32], q=⌊N/12⌋ | [NOT DEFENSIBLE]. Denominator 12 unexplained. |
| EXA R2 exhaustive 1..105 | [THEOREM/PROOF] of finite-scale coverage; [ENGINEERING ADAPTATION] as exporter. Σ_{w=1}^{105}(106−w) = 105·106/2 = **5565**/channel, ×26 = **144,690**, ×5 = **723,450** values/episode. Keep as reference upper bound. |
| GROK ACF/ESS-adaptive | Concepts [ESTABLISHED STATISTICAL RESULT]; transplant [ENGINEERING ADAPTATION]. ESS N_eff = N/(1+2Σρ_t), integral timescale, Bartlett formula are real. But at N=105: sample-ACF Var≈1/N (±0.2 bands), ~5 undeived thresholds replace 1 constant, STARVED/BLOCKED/DOWN + drift violate stationarity. Usable only as pooled, stratified diagnostic (§7). |
| CLAUDE dyadic {1,2,4,8,16,32,64} | Reconstruction [THEOREM/PROOF] for 4/5 features under conditions (§5); base-2 [ENGINEERING ADAPTATION]; any optimality claim [NOT DEFENSIBLE]. Counts: 105+104+102+98+90+74+42 = **615** windows vs 5565 → **9.05×** fewer. Correct framing (coverage, not optimality), but needs recombination contract, float-tolerance caveat, global-envelope condition. |

## 4. BEST ALTERNATIVE (Q2/Q5 — representation, not a number)

**Recommendation: `B_i=null` + sufficient-statistic sidecar + deferred selection, with pooled training-episode estimation in parallel.**

Per unresolved channel per episode export:

- `S[k] = Σ_{t<k} x[t]`, `Q[k] = Σ_{t<k} x[t]²`, k=0..N (2(N+1) floats).
- Range-min/max structure (sparse table O(N log N)/O(1), or segment tree O(N)).
- Globally precomputed envelope power `p[t] = e[t]²` (pre-registered GES2N-style definition) + prefix `P[k]`.
- Metadata: `B_i=null, scale_status=unresolved, envelope_definition_id+version, episode_id, warmup/fault masks`.

Exact O(1) answers to any legal (start,w) query for all 5 features (under Case-A envelope). ~1.7k values/channel vs 3075 (dyadic) vs 5565×5 (exhaustive). Prefix sums are the minimal exact representation for sum/sumsq.

If schema freeze forbids a sidecar: export the dyadic rolling bank as the **schema-compatible encoding of the same idea** with recombination contract + tests.

Claim: zero statistical optimality; theorem is *information preservation*, provable from data alone. Scale *selection* deferred to training consumer (supervised w per fault family — the only place labels justify choice).

## 5. EXACT MATHEMATICS (Q3/Q4 — dyadic audit with proof)

Fix `x[0..N−1]`, N=105, half-open [s,s+w), 0≤s, s+w≤N. Exporter emits for each 2^k ∈ {1,2,4,8,16,32,64} rolling sum, sumsq, min, max over [t,t+2^k) for every legal t. (Sums recoverable from means; sumsq from RMS — state in metadata.)

**Lemma (binary partition).** Any w≥1 = Σ_{j∈J} 2^j. Then [s,s+w) partitions into |J| consecutive disjoint dyadic blocks. All lie inside [s,s+w) ⊆ [0,N), hence legal (stride-1 gives every start). *Proof.* Positional decomposition; disjointness/coverage by construction. ∎

**Theorem (sums).** Sum/sumsq over [s,s+w) = sum of block sums/sumsq. Mean = sum/w, RMS = √(sumsq/w). *Proof.* Finite additivity over disjoint unions. ∎

**Theorem (min/max).** min/max over [s,s+w) = min/max of block min/max. *Proof.* min(A∪B)=min(min A,min B) by associativity/idempotence/commutativity; induction over |J|. ∎ (Overlapping sparse-table query also works — textbook RMQ fact — but disjoint partition suffices.)

Edge cases: arbitrary start/overlap covered (partition relative to s); w>64 e.g. 105=64+32+8+1, 53=32+16+4+1, 100=64+32+4, max popcount ≤4 for w≤105; **RMS needs sumsq (RMS not additive — combining RMS directly fails)**; mean needs sums; **float-exactness is FALSE as bit-identity** — IEEE-754 summation is non-associative, error O(ε·Σ|x|); assert allclose, not ==; counterexample: large-mean/small-variance cancellation reordered across blocks.

Q4 verdict: **A ✓ (exact over ℝ, 4 features, conditional 5th). B ✓ (9× fewer, O(popcount w) query). C ✗. D ✗. E ✗. F ✗.** Completeness + efficiency only.

## 6. ENVELOPE-BAND ENERGY (Q10)

- **Case A — envelope once per channel per episode (global), windowed energy = Σ p[t]:** reconstructible by additivity. **Only regime where any bank claim holds.** Matches specs: pre-registered statistic (upgrade-spec §5, R2), windowed alongside stats (training-spec §3.4). [ENGINEERING ADAPTATION with conditional proof.]
- **Case B — filter/Hilbert/envelope recomputed inside each window:** **NOT reconstructible. Counterexample:** finite-window Hilbert (FFT bins, leakage, edge transients) and filter state/ringing differ per window; E_whole ≠ concat(E_blocks), Σ sub-energies ≠ whole energy. [NOT DEFENSIBLE] to claim otherwise.

Normative: pin `envelope_definition_id + code version` in `window_config.json`; compute globally; export prefix of `p[t]`. Test that window-local recomputation is rejected (assert energy == windowed-sum(global) to tolerance). Raw-waveform matching prohibited (§9.1).

## 7. TRAINING-EPISODE POOLING (Q8 — yes, the principled fix)

**Yes, with strict conditions. Statistically the best way to address N=105; no external data.**

Single-episode ACF/periodogram variance ~1/N; pooling M training episodes ~1/(MN) under cross-episode independence (SeedSequence seeds independent by construction). M=20 at T=300 ≈ 6000 steps. [ESTABLISHED STATISTICAL RESULT.]

Protocol (constants labeled): training seeds only; fit-inside-folds, transform test (TF1 law §3.5); deterministic `SEEDS_20`; version-pinned estimator [ENGINEERING ADAPTATION]. Stratify first: RUN-normal-only, per machine/channel, exclude warmup(15), fault GT, DOWN/DROPOUT(SHF), post-maintenance transients (§3.1–3.3). Estimator: pooled ACF / averaged periodogram ("autocorrelation-hill/RobustPeriod", OQ-10 names the analysis — numbers must come from your battery). Validate B_i only if peak stable across folds/seeds, else `unresolved` (a finding about physics, not estimator failure). Every threshold (Bartlett lag, ESS floor, prominence, min-episodes) = engineering choice + sensitivity sweep. Pooled estimation finds *predictive* scales, not *detection-optimal* scales (those need labels — durations 8–25 — in the consumer).

## 8. ARCHITECTURE (Q6/Q7/Q9)

```
B_i reliable   → B_i = b, status = resolved → 0.5b, b, 2b (unchanged rows)
B_i unresolved → B_i = null, status = unresolved → neutral cover
                  (preferred: prefix/RMQ sidecar; alt: dyadic 1..64 rolling rows
                   under separate column family / schema bump),
                  downstream DEFERS scale choice (supervised search in grouped CV,
                  purge/embargo = 1 window; or interval max-pool if CI supplied).
```

- **Q7 (B=null + defer): yes — most scientifically honest default.** Strictly more honest than any invented B.
- **Q9 (interval [L_i,U_i]): coherent as uncertainty wrapper, not theorem.** Cover scales intersecting [0.5L_i, 2U_i]; consumer max-pools/selects inside. Do NOT claim nominal coverage (e.g. 95% CI) unless mixing/stationarity verified + calibrated on held-out training episodes — else [ENGINEERING ADAPTATION/HEURISTIC]. Collapses to current path when L=U=B: architecture preserved.

## 9. IMPLEMENTATION

- **`src/window_export.py` (new):** pure `rolling_bank(x,W)`, `prefix_repr(x,p)`, `reconstruct(...)`, `global_envelope(x, definition_id)`; no RNG/I/O; offline deterministic. W constant comments cite this audit (representation, not physics).
- **Schema:** add `B_i (nullable)`, `scale_status`, `scale_cover`, `envelope_definition_id+version` to `window_config.json`; unresolved → sidecar/dyadic columns, never fabricated B_i. Schema bump (v4→v5 if touching v4) + CI assertion; extend flag-day readers.
- **Training consumer (MINIPRO-19):** branch on `scale_status`: resolved → 0.5B/B/2B; unresolved → query any w from cover (deferred supervised search in grouped CV, purge/embargo per §3.4). No test information in cover.
- **Coordination:** M0.2f owned fields gain `scale_status/B_i/envelope_definition_id`; M0.2e prohibition unchanged; rebase/second-lander rule unchanged.

## 10. TESTS

1. Reconstruction property: seeded random episodes, all (s,w): block-recombined mean/RMS/min/max vs direct → `allclose` (fail on `==`). Include w∈{1,53,64,65,100,105}, odd starts, max overlap.
2. Float non-identity: adversarial large-offset/tiny-variance case where block-sum ≠ naive-sum bitwise but passes tolerance.
3. RMS-needs-sumsq: direct RMS combining must fail; sumsq combining must pass.
4. Envelope A/B: windowed-sum(global) == reconstruction (pass); window-local recompute == reconstruction (must FAIL).
5. No-fabrication: unresolved → `B_i is null`, no 0.5B/B/2B columns, cover present + versioned.
6. Leakage (existing pattern): cover/pooled-B fit on train seeds only; episode-recovery ≤ chance+2pp; refit detection; SMOTE-inside-folds.
7. Counts/schema: 615 vs 5565 at N=105; config pins estimator + envelope IDs; duplicate-writer guard extended.

## 11. VIVA DEFENCE (30s)

"No single window derives from N=105 alone — a one-sample pulse wants w=1, a sustained anomaly wants w=L, and the matched filter proves the optimum needs the signal model, which N lacks. So we export no invented B: resolved channels keep 0.5B/B/2B; unresolved export B=null with a dyadic/prefix cover provably reconstructing every legal window's mean, RMS, min, max — and envelope energy when the pre-registered envelope is computed once per channel — deferring scale choice to supervised training. Base-2 is engineering compression, not physics. Pooled training-episode estimation is the only legitimate uncertainty reducer, under strict no-leakage stratification."

## 12. WHAT WE MUST NOT CLAIM (+ self-disproof)

Never: dyadic scales optimal/physical; base-2 required (any base works — 2 minimizes block-count vs table-size tradeoff only); float reconstruction bit-exact; window-local envelope reconstructs; N^(2/3)/N/12/N/8 constants derived; single-episode ESS/ACF thresholds are theorems; pooled-B CIs have nominal coverage uncalibrated; prefix sums alone answer min/max (non-invertible — hence RMQ).

Against this recommendation: prefix/RMQ sidecar is the largest schema change; fallback = dyadic rolling bank (same theorems, schema-compatible, 9× cheaper than exhaustive); last resort = exhaustive 1..105 reference bound (723k values/episode disclosed). All dominate inventing a number; none claims optimality.

## Sources

- Sparse-table idempotence + O(1) query (cp-algorithms; Stanford CS166 slides; Jeffe RMQ notes).
- Matched-filter SNR optimality via Cauchy–Schwarz (TUM LNT Theory of Stochastic Signals; Neyman–Pearson via 2107.09378 review).
- ESS N/(1+2Σρ) + integrated autocorrelation time (Stan Reference Manual; MCMC/ESS literature; arXiv 2408.13411).
- Bartlett (1935) sampling properties of autocorrelated series; effective-observations overview (Metrology 2010).
