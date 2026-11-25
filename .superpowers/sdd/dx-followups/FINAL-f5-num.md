# FINAL-f5-num — numeric-hazard audit of the delay STARVED-mass gate (READ-ONLY)

Source worktree: `m0b-t-build`. F5 lane owns `src/possibility.py`,
`tests/test_possibility.py`, `probe_delay.py`. This report makes ZERO edits
to those files, runs NO pytest, touches NO Linear, commits NOTHING.
Read-only sources: `tests/test_possibility.py:71-117` (5 gate tests),
`src/possibility.py` (379 lines, fully read — NO `assert_delay_starved_mass`
exists yet; healthy TDD-RED), `probe_delay.py` (42 lines, fully read),
`.superpowers/sdd/dx-followups/FINAL-probeassist.md` (gate sketch + probe counts).

## Gate contract under audit

Per `tests/test_possibility.py:71-117` and `FINAL-f5-linear.md:3-10`:

- Conservation: `starved <= injected * n_downstream`, else `CONSERVATION`.
- Visibility: `starved + shield >= injected`, else `VISIBILITY`.
- `n_downstream == 0` → `{"ok": True, "side": "vacuous"}`.
- Pinned cases: `(4,6,2)→ok`; `(2,9,2)→CONSERVATION`; `(6,1,2,shield=0.0)→VISIBILITY`;
  `(6,1,2,shield=6.0)→ok/shielded`; `(6,0,0)→ok/vacuous`.

Reference sketch: `FINAL-probeassist.md:86-124` —
`assert_delay_starved_mass(injected_steps: float, starved_steps: float,
n_downstream: int, buffer_shield_steps: float = 0.0, *, tol: float = 1e-9)`,
conservation as `starved - injected*n > tol` (:111), visibility as
`starved + shield + tol < injected` (:115), vacuous early-return on `n == 0`
(:108-110).

## H1 — float-vs-int hazard (throughput-derived floats feeding integer comparisons?)

**Verdict: PRESENT — latent wiring hazard, not a live defect.**

- No live defect exists: the gate function itself is absent from
  `src/possibility.py`, and all 5 pinned test inputs are exact ints except
  `buffer_shield_steps=0.0/6.0` (`test_possibility.py:100,107`). Integer
  comparisons cannot misfire on these pins.
- The hazard is real at the wiring boundary. `probe_delay.py:26-28`
  derives float rates (`pre['tput_C2'].sum() / 60.0` → 0.167 ≈ 1/6,
  non-terminating in binary), `:32-34` derives float masses
  (`with_O`, `miss_6/7` → 0.83/0.50/1.00/1.67/−0.17/−0.50 per
  `FINAL-probeassist.md:29-36`), `:38` derives float `bufq`, while only
  `S_starved` is a true int count (`:35-36`, `int(...)`).
- `FINAL-probeassist.md:38-44,126-131` already documents the trap:
  throughput-miss units (0–2) ≪ STARVED steps (3–9); the gate "must compare
  *steps to steps* with fan-out multiplier, not units to steps". Feeding
  `with_O`/`sum_miss` floats into `injected_steps`/`starved_steps` (both
  typed `float` in the sketch, `:87-88`) while reasoning in integer steps
  silently changes both legs' outcomes (e.g. ep 41242 `with_O=0.50`,
  `sum_miss=0.00`, `S=3` — three different numbers for "the delay mass").
- Guard status: discipline + `tol` mitigate, but only if F5 keeps
  `injected_steps` dur-like (integer steps) and `starved_steps = S`
  (integer STARVED-step sum over downstream machines, `n_downstream` = 2
  for C2→C6/C7), with `buffer_shield_steps` as pre-onset queued cover
  (`bufq`, possibly rate-scaled per probeassist `:132-133` — itself a
  float source). Recommendation: keep float-typed params with `tol`
  (never `int()`-truncate inputs at the gate boundary; truncation biases
  the visibility leg downward), and never substitute a throughput-miss
  float for a step count.

## H2 — division-by-zero (`n_downstream == 0` handled by vacuous branch?)

**Verdict: ABSENT — no division exists, and the vacuous guard is correctly ordered.**

- The sketch performs zero divisions: conservation is multiplication
  (`injected_steps * n_downstream`, `:111`), visibility is addition
  (`:115`). `n_downstream == 0` needs no arithmetic guard at all;
  the early return at `:108-110` precedes both comparisons, so
  `(6,0,0)→ok/vacuous` (`test_possibility.py:111-117`) passes structurally.
- Grep over `src/` finds no `/ n_downstream` or per-machine averaging
  anywhere near the gate (function absent; no sibling code divides by it).
- Standing constraint for F5: keep it that way. A "natural" refactor to
  per-machine averages (`starved / n_downstream`) would reintroduce a
  divide-by-zero exactly on the sink-origin path (tails, PKG, ASM2 —
  probeassist `:138-139`) that the vacuous leg exists to protect. The
  multiplicative form `starved <= injected * n` is the zero-safe form;
  do not normalize.

## H3 — epsilon tolerance needed?

**Verdict: PRESENT as a production-wiring requirement; ABSENT as a requirement
for the 5 pinned tests.**

- For the pinned integer cases, `tol` is inert: margins are ≥1
  (conservation gaps 9−4=5, 8−6=2; visibility gaps 6−1=5, and 1+6−6=1).
  `tol=1e-9` flips none of the 5 outcomes — correctly so; the tests pin
  exact-step semantics.
- For production wiring, `tol` is required, and the sketch already carries
  it (`tol: float = 1e-9`, `:92`; applied one-sided at `:111` and `:115`).
  Evidence: probe masses are non-integers (`0.83`, `0.50`, `1.67`,
  `FINAL-probeassist.md:29-36`); baseline rate 1/6 is non-terminating in
  binary so `rate*L − Σtput` accumulates representation error; a
  rate-scaled shield (`buffer_C26+buffer_C67` scaled by rate, probeassist
  `:132-133`) compounds it. A strict `<`/`>` on such floats misfires
  within ~1e-15 of any boundary (e.g. a shielded case landing at
  `starved+shield == injected ± ε`).
- Application direction in the sketch is correct (does not mask real
  violations): conservation raises only when `starved` exceeds the fence
  by *more than* `tol`; visibility raises only when the shortfall exceeds
  `tol`. Recommendation: keep `tol=1e-9` as a keyword-only param; do NOT
  enlarge it to cover the `H=30` window inflation noted at probeassist
  `:135-137` — that is a windowing bias (recovery starvation inflating S),
  not representation noise, and must be fixed by bounding the window, not
  by slack.

## Tally

| # | Hazard | Verdict |
|---|--------|---------|
| H1 | float-vs-int (throughput floats into step comparisons) | PRESENT (latent wiring; absent as live defect — function not yet implemented) |
| H2 | division-by-zero on `n_downstream == 0` | ABSENT (no division; vacuous early-return correctly ordered) |
| H3 | epsilon tolerance | PRESENT for production wiring (sketch already has `tol=1e-9`); ABSENT for the 5 pinned integer tests (margins ≥1) |

**Hazard count: 2 present (H1 latent, H3 conditional) out of 3 assessed; H2 absent.**

Constraints honored: no writes to `src/possibility.py`,
`tests/test_possibility.py`, or `probe_delay.py`; no pytest run; no commits;
no Linear access. Only new file is this report.
