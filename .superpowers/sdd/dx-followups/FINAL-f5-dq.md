# FINAL-f5-dq — DIAGNOSIS_QUALITY.md F5 record (DRAFT, file only — DQ untouched)

Owner: F5 lane. Status at draft time: RED ( `assert_delay_starved_mass` not yet
implemented in `src/possibility.py`; 5 tests in `tests/test_possibility.py:71-117`
define the contract). This file is the paste-ready DQ record. DO NOT edit
`docs/DIAGNOSIS_QUALITY.md` from this lane — controller/owner applies on GREEN.

## Gate rules (conservation + visibility, steps-to-steps)

`assert_delay_starved_mass(injected_steps, starved_steps, n_downstream,
buffer_shield_steps=0.0, tol=1e-9)`:

- CONSERVATION (no starvation from nothing):
  `starved <= injected * n_downstream + tol`, else raise `AssertionError("CONSERVATION ...")`.
- VISIBILITY (no silent / decoupled delay; only when `n_downstream > 0`):
  `starved + buffer_shield_steps + tol >= injected`, else raise
  `AssertionError("VISIBILITY ...")` (delay went to caps/backpressure/failover).
- VACUOUS: `n_downstream == 0` → `{"ok": True, "side": "vacuous"}` (sink origins:
  tails, PKG, ASM2 — no line-internal downstream, nothing to check).
- Sides on pass: `"visible"` (default), `"shielded"` iff `shield > tol` and
  `starved < injected`, `"vacuous"` iff `n == 0`.
- Units discipline: compare STARVED *steps* summed over downstream machines to
  injected busy/delay *steps* with fan-out multiplier `n_downstream`. Do NOT
  compare throughput-miss units to STARVED steps (probe shows units 0–2 ≪ steps 3–9).

## Pinned constants (contract pins from `tests/test_possibility.py:71-117`, n/seed lineage)

| # | test | inputs (injected, starved, n, shield) | pinned outcome |
|---|---|---|---|
| 1 | `test_delay_starved_mass_holds_on_visible_delay` (:71) | (4, 6, 2, 0.0) | `ok=True` (visible: 6 ≤ 4×2; 6 ≥ 4−0) |
| 2 | `test_delay_starved_mass_rejects_starvation_from_nothing` (:81) | (2, 9, 2, 0.0) | raises `AssertionError` match `CONSERVATION` (9 > 2×2) |
| 3 | `test_delay_starved_mass_flags_buffer_decoupled_delay` (:91) | (6, 1, 2, 0.0) | raises `AssertionError` match `VISIBILITY` (1+0 < 6, empty buffers) |
| 4 | `test_delay_starved_mass_shielded_delay_passes` (:103) | (6, 1, 2, 6.0) | `ok=True`, `side="shielded"` (stocked buffers absorb) |
| 5 | `test_delay_starved_mass_vacuous_without_downstream` (:111) | (6, 0, 0, 0.0) | `ok=True`, `side="vacuous"` |

Lineage: pins 1–5 are analytic contract cases (n = 5 assertions, no stochastic
fit, no seed — deterministic gate). Topology pin: C2→C6→C7 via buffers C26/C67
(`twin.py`); `n_downstream=2` for C2 delay. Empirical grounding below is
observational (n=6 probe episodes), not a fitted constant: `buffer_shield_steps`
stays an explicit parameter.

## Probe numbers (`probe_delay.py`, 42 lines, read-only run)

Method: manifest `docs/m0b_mass_full_manifest.json` first 6 rows with
`class=='delay'`, `origin=='C2'` → `(t0, dur)`; traces
`artifacts/m0b_mass_c*.parquet` column-filtered
(`episode_id, step, state_C2/C6/C7, tput_C2/C6/C7, buffer_C26/C67`), early-break
at 6/6 found. Baseline rates from 60 pre-onset steps (`rate=tput.sum()/60`).
Window `L=dur+H`, `H=30`: `with_O=rate_O·L−Σtput_C2`,
`miss_6/7=rate_6/7·L−Σtput_C6/7`, `S=#(state_C6==STARVED)+#(state_C7==STARVED)`
over `[t0,t0+dur+H)`, `bufq=buffer_C26+buffer_C67` at `t0−1`.
Battery lineage: frozen T=300 (`m0b_mass_*.parquet`, 4200 fault + 600 clean
episodes) per DQ header; probe slice n=6, deterministic read (no sampling seed).

| ep | with_O | miss6 | miss7 | sum_miss | S_starved | bufq |
|----|--------|-------|-------|----------|-----------|------|
| 41218 | 0.83 | 0.83 | 0.83 | 1.67 | 7 | 2.0 |
| 41220 | 0.50 | 0.50 | 0.50 | 1.00 | 7 | 0.0 |
| 41221 | 1.00 | 1.00 | 0.00 | 1.00 | 9 | 0.0 |
| 41242 | 0.50 | 0.50 | −0.50 | 0.00 | 3 | 0.0 |
| 41281 | 0.83 | 0.83 | −0.17 | 0.67 | 3 | 0.0 |
| 41291 | 1.00 | 1.00 | 1.00 | 2.00 | 9 | 0.0 |

Findings: baseline rate 0.167 everywhere (≈1 unit/6 steps). With `bufq≈0` (5/6
exactly 0.0, one 2.0), every C2 delay is visible downstream as S=3–9 STARVED
steps across C6+C7 — the visible-delay regime exists empirically. (a) S (3–9)
overstates throughput-miss units (0–2.0) → steps-to-steps with fan-out `n` is the
correct comparison. (b) Ep 41242 (`with_O=0.50`, `sum_miss=0.00`, `S=3`) is the
decoupled specimen — withheld mass that never shows as downstream miss, exactly
what the VISIBILITY leg (pin 3) must catch. (c) No stocked-buffer episode in
this slice (`bufq≤2`) → the shielded leg (pin 4) cannot be calibrated from these
6 and stays a parameter (`buffer_shield_steps` = pre-onset queued cover, e.g.
`bufq` possibly rate-scaled). (d) `H=30` inflates S with recovery starvation —
keep any episode-feature wiring window-bounded; do not bake H into the assertion.

## Disposition — path-tuning trust gate

- `side="visible"` (pins 1–2 boundary): TRUST — conservation holds and delay is
  visible; episode may feed path tuning (`best_cause_path`/`best_path`/`rank_nodes`).
- `CONSERVATION` trip (pin 2): DISTRUST input — starvation from nothing;
  fail loud, do not tune on the episode.
- `VISIBILITY` trip (pin 3, specimen ep 41242): DISTRUST episode — delay
  deflected to caps/backpressure/failover; path tuning must NOT trust it.
- `side="shielded"` (pin 4): TRUST-WITH-ATTRIBUTION — absorbed by stocked
  buffers; pass only when `buffer_shield_steps` cover is explicitly supplied.
- `side="vacuous"` (pin 5): SKIP — sink origin, no downstream; nothing to gate.

## Paste-ready DQ insertion (for owner on F5 GREEN)

Suggested section `## Delay→STARVED mass gate (MEASURED <date>, F5, n=6 probe)`:
conservation `S ≤ injected×n` + visibility `S+shield ≥ injected` (+ vacuous
`n==0`); pins (4,6,2)→ok / (2,9,2)→CONSERVATION / (6,1,2,0)→VISIBILITY /
(6,1,2,6)→shielded / (6,0,0)→vacuous; probe table above (S 3–9, bufq≈0,
specimen 41242); shield stays a parameter; disposition: visible→trust,
VISIBILITY/CONSERVATION→distrust for path tuning, shielded→trust-with-cover,
vacuous→skip. Lineage: `tests/test_possibility.py:71-117`,
`probe_delay.py:1-42`, manifest `docs/m0b_mass_full_manifest.json` (delay/C2×6),
`artifacts/m0b_mass_c*.parquet`, battery frozen T=300 (4200/600).

Constraints honored: no edits to `docs/DIAGNOSIS_QUALITY.md`,
`src/possibility.py`, `tests/test_possibility.py`, or `probe_delay.py`; no
commits; no pytest; no Linear.
