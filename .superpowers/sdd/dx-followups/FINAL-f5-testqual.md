# FINAL-f5-testqual — mutation review of tests/test_possibility.py lines 71–117

Scope: read-only review of the 5 `assert_delay_starved_mass` tests in worktree
`m0b-t-build`. No edits to `src/`, `tests/`, or `probe_delay.py`; no pytest run;
no commits; no Linear. Reference implementation logic taken from the agreed
contract (FINAL-probeassist sketch + test comments):
conservation `starved <= injected * n + tol` else `AssertionError("CONSERVATION…")`;
visibility `starved + shield >= injected - tol` else `AssertionError("VISIBILITY…")`;
`n == 0 → {"ok": True, "side": "vacuous"}` first; `side` = `shielded` iff shield
explains the gap, else `visible`.

Test shorthand:
- T1 L71 `holds_on_visible`: `(4, 6, 2)` → `ok is True` (default shield 0.0).
- T2 L81 `rejects_starvation_from_nothing`: `(2, 9, 2)` → raises, `match="CONSERVATION"`.
- T3 L91 `flags_buffer_decoupled`: `(6, 1, 2, shield=0.0)` → raises, `match="VISIBILITY"`.
- T4 L103 `shielded_passes`: `(6, 1, 2, shield=6.0)` → `ok is True`, `side == "shielded"`.
- T5 L111 `vacuous_without_downstream`: `(6, 0, 0)` → `ok is True`, `side == "vacuous"`.

## Mutant-by-mutant kill table

1. **Always-return-ok** (never raises; e.g. `return {"ok": True, ...}` unconditionally).
   - **Caught by T2 and T3.** T2 expects a `CONSERVATION` raise, gets `ok` — fail.
     T3 expects a `VISIBILITY` raise, gets `ok` — fail. Two independent kills;
     T1/T4/T5 still pass (as they should on correct code), so the mutant is
     unambiguously detected.
2. **Swapped inequalities** (any of: conservation `<` for `>`; visibility `>` for
   `<`; legs transposed so conservation enforces the visibility bound and vice versa).
   - **Caught by T1 + T2 + T3 (each leg-swap trips at least two).**
     - Conservation flipped (`raise iff starved < injected*n`): T1 `(4,6,2)` has
       `6 < 8`, so it falsely raises — T1 fails; T2 `(2,9,2)` has `9 < 4` false, so
       it fails to raise — T2 fails.
     - Visibility flipped (`raise iff starved+shield > injected`): T1 `6 > 4`
       falsely raises — T1 fails; T3 `1 > 6` false, fails to raise — T3 fails;
       T4 `1+6=7 > 6` falsely raises — T4 fails.
     - Legs transposed: same signature — the pass-case T1 becomes a raise and at
       least one raise-case becomes a pass. No single-swap mutant survives all five.
3. **Missing vacuous branch** (`if n_downstream == 0: return vacuous` deleted;
   falls through to the normal legs, or hits `ZeroDivision`/generic error path).
   - **Caught by T5 alone (uniquely).** Correct legs on `(6, 0, 0)`: conservation
     `0 <= 0` passes, visibility `0 + 0 < 6` raises `VISIBILITY` — but T5 demands
     `ok/vacuous`, so it fails. Any division-by-`n` variant errors instead of
     returning — T5 still fails. No other test uses `n == 0`, so T5 is the sole
     guard and it holds.
4. **Missing shield term** (visibility checked as `starved < injected`, shield
   parameter accepted but ignored).
   - **Caught by T4 alone (uniquely).** T4 `(6, 1, 2, shield=6.0)`: ignoring shield,
     `1 < 6` raises `VISIBILITY` — but T4 demands `ok/shielded`, so it fails.
     T3 (shield 0.0) is unaffected, confirming the kill is shield-specific and not
     a generic visibility break.
5. **Wrong match strings** (messages swapped between legs, misspelled keywords, or
   generic `AssertionError`/custom exception without `CONSERVATION`/`VISIBILITY`).
   - **Caught by T2 + T3 jointly.** T2 asserts `match="CONSERVATION"`, T3 asserts
     `match="VISIBILITY"` (`pytest.raises` does `re.search` on `str(exc)`).
     Swapped labels fail both matches; keyword-free messages fail both; a
     non-`AssertionError` exception type also fails both `pytest.raises` blocks.
     T1/T4/T5 (no `raises`) are blind to this mutant, but T2/T3 cover it exactly.

## Verdict: SUFFICIENT

Every listed mutant is killed by at least one test, and three of the five have
dedicated unique guards (T4→shield, T5→vacuous, T2/T3→labels). The set forms a
minimal cover: drop any one test and a mutant escapes (drop T5 → vacuous-less
passes; drop T4 → shield-less passes; drop T2 or T3 → always-ok half-covered and
label-swaps half-blind; drop T1 → flipped-inequality false-positive undetected).

## Non-blocking hardening gaps (beyond the five mutants, no new test demanded here)

- T1 asserts only `ok is True`, not `side == "visible"` — a wrong-side mutant
  (`visible` cases reported `shielded`) slips T1 and is only caught indirectly
  via T4/T5 side checks. Adding `and out["side"] == "visible"` to T1 would close
  it for free; F5 owner decides.
- Boundary/tolerance behavior (`starved == injected*n` exactly, `starved+shield == injected`
  exactly) and degenerate inputs (`injected == 0`, e.g. `(0, 1, 2)` must raise
  `CONSERVATION`; `(6, 5, 0)` vacuous-vs-conservation precedence) are unexercised.
  None of the five in-scope mutants hides there, so the set is sufficient as
  specified — these are optional extras, not missing required cases.

Return: **sufficient** — no missing case among the five mutant classes.
