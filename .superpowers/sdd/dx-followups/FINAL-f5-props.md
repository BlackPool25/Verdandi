# FINAL-f5-props — boundary behaviors of `assert_delay_starved_mass` (READ-ONLY analysis)

Source: pinned cases in `tests/test_possibility.py` lines 71–117.
Gate under analysis (per task contract, no code written or executed here):

```text
assert_delay_starved_mass(injected, starved, n_downstream, buffer_shield_steps=0.0)
  1. vacuous:  if n_downstream == 0 -> ok/vacuous (nothing to check)
  2. CONSERVATION: if starved > injected * n -> raise (no starvation from nothing)
  3. VISIBILITY:   if starved < injected - shield -> raise (delay went to caps/backpressure/failover)
  else ok (side = visible | shielded)
```

Rule order assumed: vacuous first, then CONSERVATION, then VISIBILITY
(matches the sketch in FINAL-probeassist §3 and the pinned tests).
Float equality understood with a small tolerance; it does not change any
verdict below except to absorb rounding noise.

Pinned references:
- (4, 6, 2) -> ok (visible-delay regime).
- (2, 9, 2) -> CONSERVATION (9 > 2*2).
- (6, 1, 2, shield=0.0) -> VISIBILITY (1 < 6-0).
- (6, 1, 2, shield=6.0) -> ok/shielded (1+6 >= 6).
- (6, 0, 0) -> ok/vacuous.

## 1. injected=0, starved=0

- n == 0 -> vacuous ok. Dictated: rule 1 short-circuits before any arithmetic.
  Sane for path-tuning trust: YES — sink origins (tails/PKG/ASM2) have no
  downstream to conserve against; trusting nothing-to-check is correct.
- n > 0, shield=0 -> passes both legs: 0 <= 0*n (CONSERVATION holds as
  equality); 0 < 0-0 is false (VISIBILITY holds as equality) -> ok/visible.
  Sane: YES — no delay injected, none observed; episode carries no
  delay-mass evidence either way, and passing (rather than flagging) avoids
  false distrust of clean episodes.

## 2. starved=0 with n > 0 (injected > 0)

- shield=0 -> CONSERVATION passes (0 <= injected*n), VISIBILITY raises
  (0 < injected). Dictated: VISIBILITY failure.
  Sane: YES — this is the extreme end of the pinned decoupled-delay family
  (cf. (6,1,2,shield=0) -> VISIBILITY). Injected delay that leaves zero
  downstream STARVED with no buffer cover means the mass went somewhere the
  path-tuner cannot see (caps/backpressure/failover); distrusting the episode
  is exactly the tripwire's job.
- 0 < shield < injected -> still VISIBILITY (0+shield < injected).
  Sane: YES — partial cover does not excuse full disappearance.
- shield >= injected -> ok/shielded (0+shield >= injected).
  Sane: YES — stocked buffers fully explain absorption; trust with the
  shielded side-flag so downstream consumers know *why* it passed.

## 3. Negative inputs (invalid caller data; all fail closed)

- injected < 0 (starved >= 0, n > 0): CONSERVATION bound injected*n is
  negative, so any non-negative starved exceeds it -> CONSERVATION raise
  (except n==0, which is vacuous). Dictated: raise.
  Sane: YES (trust-safe). Negative injected steps are non-physical; loud
  rejection keeps a corrupt episode out of path tuning. Only nit: the label
  says CONSERVATION rather than ValueError, but the fail-closed direction is
  what matters for trust.
- starved < 0 (injected >= 0): CONSERVATION passes (negative <= bound);
  VISIBILITY raises (negative < injected-shield for any sane shield).
  Dictated: VISIBILITY raise. Sane: YES — same reasoning; invalid input
  fails loud instead of passing as clean.
- n_downstream < 0: not == 0, so no vacuous leg; CONSERVATION bound is
  negative -> almost surely CONSERVATION raise. Dictated: raise.
  Sane: YES — negative fan-out is a caller bug; rejecting is safe.
- buffer_shield_steps < 0: threshold injected-shield grows above injected,
  making VISIBILITY strictly harder to satisfy -> raise (or demand more
  starved). Dictated: raise (fail-closed). Sane: YES — negative cover is
  non-physical and must not smuggle an episode through.

## 4. Floats (fractional steps / rate-scaled mass)

- Rules are pure arithmetic (multiply, subtract, compare), so floats flow
  through identically to ints; tol absorbs representation noise
  (e.g. probe-scale values like injected=0.83, starved=7 borrow no
  integer-only assumption). Boundary equality within tol passes.
  Dictated: same verdicts as the nearest exact values.
  Sane: YES — probe output is fractional (with_O/miss in units of ~0.167);
  a gate that choked on floats would be unusable at calibration time.

## 5. Huge values (e.g. 1e12 / 1e18 steps)

- CONSERVATION scales linearly (injected*n); VISIBILITY is a difference.
  Python ints are arbitrary-precision and floats saturate to inf rather than
  wrap, so no overflow inversion: huge-but-consistent pairs pass, huge
  starved from tiny injected still raises CONSERVATION, huge injected with
  tiny starved still raises VISIBILITY.
  Dictated: verdicts scale with the ratios, unchanged in kind.
  Sane: YES — step counts in practice are single/double digits, so this
  regime never binds; the gate degrades gracefully (no wrap-to-pass).
  Caveat noted, not insane: at float-huge magnitudes tol is negligible vs
  rounding, so near-equality could false-trip VISIBILITY — irrelevant for
  path tuning because real inputs are small exact counts.

## 6. shield > starved (buffer cover exceeds observed starvation)

- Pinned case is exactly this: (6, 1, shield=6.0) -> 1 < 6 but 1+6 >= 6 ->
  ok/shielded. General rule: shield excuses disappearance only up to its own
  cover — passes iff starved+shield >= injected, else VISIBILITY.
  Sane: YES — this is the absorption leg working as designed: stocked
  buffers (pre-onset buffer_C26+buffer_C67 cover) explain why injected delay
  never surfaced as STARVED, so the episode is trustworthy *as shielded*
  rather than silently trusted as visible.
- shield > injected (over-cover, e.g. starved >= injected so side stays
  visible): still ok; over-cover does not mislabel or force-pass a
  conservation violation. Sane: YES.

## Verdict

Count of insane outcomes (boundary behavior whose dictate would corrupt
path-tuning trust): **0**.

Every boundary either passes a genuinely clean/absorbed episode or fails
loud in the distrust direction; no boundary passes a decoupled or
from-nothing episode, and no valid clean episode is flagged.
