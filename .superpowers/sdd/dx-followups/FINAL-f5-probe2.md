# FINAL-f5-probe2 — test↔episode grounding map (READ-ONLY)

Source worktree: `m0b-t-build`. No edits, no commits, no tests, no Linear.
Inputs fully read: `probe_delay.py` (42 lines), output table in
`.superpowers/sdd/dx-followups/FINAL-probeassist.md`, `tests/test_possibility.py` lines 71–117.

## Probe reference (probe_delay.py output, 6/6 found)

Baseline rate ≈0.167 everywhere (≈1 unit / 6 steps). Window `[t0, t0+dur+30)`.
`S_starved` = STARVED steps summed over C6+C7. `bufq` = buffer_C26+buffer_C67 at `t0-1`.

| ep | with_O | miss6 | miss7 | sum_miss | S_starved | bufq |
|----|--------|-------|-------|----------|-----------|------|
| 41218 | 0.83 | 0.83 | 0.83 | 1.67 | 7 | 2.0 |
| 41220 | 0.50 | 0.50 | 0.50 | 1.00 | 7 | 0.0 |
| 41221 | 1.00 | 1.00 | 0.00 | 1.00 | 9 | 0.0 |
| 41242 | 0.50 | 0.50 | −0.50 | 0.00 | 3 | 0.0 |
| 41281 | 0.83 | 0.83 | −0.17 | 0.67 | 3 | 0.0 |
| 41291 | 1.00 | 1.00 | 1.00 | 2.00 | 9 | 0.0 |

Key probe facts used below: (a) with `bufq≈0`, every C2 delay is visible
downstream as S=3–9 STARVED steps — visible-delay regime exists; (b) ep 41242
is a live decoupling specimen (`with_O=0.50` yet `sum_miss=0.00`, `S=3`,
`bufq=0.0`) — withheld mass that never shows as downstream miss; (c) no
stocked-buffer episode in this slice (`bufq≤2.0`), so no calibration basis for
absorption; (d) S counts *steps* (3–9), throughput-miss counts *units* (0–2) —
do not equate them.

Honesty note on "grounded": no test tuple `(injected, starved)` is
value-identical to any measured `(with_O, S_starved)` pair (tests use
stylized busy-step integers 2/4/6; probe `with_O` is 0.50–1.00 miss-units).
"grounded-in-ep-X" below therefore means **regime/pattern-grounded**
(the episode exhibits the phenomenon the test encodes), not numeric identity.

## Test↔episode map (5 tests, lines 71–117)

| # | test (args → expectation) | motivating episode(s) | verdict |
|---|---------------------------|-----------------------|---------|
| 1 | `test_delay_starved_mass_holds_on_visible_delay` (L71–78): `(4, 6, 2) → ok` | eps 41218 (S=7, bufq=2.0), 41220 (S=7, bufq=0.0), 41221 (S=9, bufq=0.0), 41291 (S=9, bufq=0.0) — empty-buffer visible-delay regime: modest injected busy-steps fan out to S ≤ injected×n_downstream | **grounded-in-ep-41218/41220/41221/41291** (primary analogues 41218/41291 per probeassist; numbers stylized: 6 ≤ 4×2) |
| 2 | `test_delay_starved_mass_rejects_starvation_from_nothing` (L81–88): `(2, 9, 2)` must raise `CONSERVATION` | none — counterfactual fence: no episode shows S=9 from ~2 injected steps without multiplier violation; probe bounds only the allowed side | **synthetic** (negative/boundary case, motivated by absence) |
| 3 | `test_delay_starved_mass_flags_buffer_decoupled_delay` (L91–100): `(6, 1, 2, shield=0.0)` must raise `VISIBILITY` | ep 41242 (with_O=0.50 > 0 but sum_miss=0.00, S=3 tiny, bufq=0.0) — delay mass vanishes with empty buffers ⇒ caps/backpressure/failover; secondary partial analogue ep 41281 (sum_miss=0.67, S=3, bufq=0.0) | **grounded-in-ep-41242** (secondary 41281; numbers sharpened to 6-vs-1 tripwire) |
| 4 | `test_delay_starved_mass_shielded_delay_passes` (L103–108): `(6, 1, 2, shield=6.0) → ok/shielded` | none — probe has NO stocked-buffer case (max bufq=2.0 in ep 41218); shield term must stay an explicit uncalibrated parameter | **synthetic** (parameter-contract case with no empirical calibration basis) |
| 5 | `test_delay_starved_mass_vacuous_without_downstream` (L111–117): `(6, 0, 0) → ok/vacuous` | none in probe scope — all 6 probe eps are C2-origin with n_downstream=2; sink origins (tails/PKG/ASM2, n=0) confirmed via topology (`twin.py` C2→C6→C7), probe trivially agrees (nothing to count) | **synthetic** (topology-contract case outside probe slice) |

## Summary

- Grounded (pattern-level): tests 1, 3 → **2/5**.
- Synthetic (boundary/contract cases with no direct episode): tests 2, 4, 5 → 3/5.
- **Grounded count: 2/5.**

Constraints honored: read-only on `probe_delay.py`, `src/possibility.py`,
`tests/test_possibility.py`; no pytest run; no commits; no Linear; only new
file is this report.
