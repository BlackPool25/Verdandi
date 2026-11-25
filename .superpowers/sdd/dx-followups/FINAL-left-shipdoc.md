# FINAL left-shipdoc — do SHIP_STATUS / ARCH / REPORT need an F5 row? (read-only verdict, no edits made)

Source worktree: `m0b-t-build` @ `9fd75f0` ("feat: delay STARVED-mass gate (F5 GREEN 9/9) + DQ record + wave reports").
F5 state at commit: `assert_delay_starved_mass` defined once (`src/possibility.py:382`), pinned by 9/9 tests
(`tests/test_possibility.py:71-117`), **0 production callers** (only `def` site matches in `src/`; tests import it,
tests are not call sites). DQ record filed `docs/DIAGNOSIS_QUALITY.md:315-321`, disposition: "trust gate for path
tuning; call-site wiring is follow-up". `docs/demo-evidence/SUMMARY.md:39` already notes GREEN + wiring follow-up.

Verdict: **change-needed NO** — silence in the three ship docs is the correct representation right now.

## (1) Contradiction check — no existing row/claim is contradicted

- `docs/SHIP_STATUS.md` §1 path row ("ABSTAIN, diagnostic-only … 0.072/0.287 … teleport Δ+0, flips wash out") and
  §2 path struck row ("diagnostic-only stands … re-baseline before any future path work"): F5 moves no number and
  changes no disposition. The gate is a trust fence *for* future path tuning, not a path-performance result. Both
  rows remain true.
- `docs/PROJECT_ARCHITECTURE.md` §8 (paths diagnostic-only, never the verdict path) and §9 (alarm-flow routing via
  calibrated-conf gate): F5 is unwired, so it correctly appears in neither the verdict path nor the routing. No claim
  of the form "no possibility gates exist" appears anywhere; nothing to contradict.
- `docs/PROJECT_REPORT.md` §7 item 2 (routes struck/diagnostic-only) and §8 scope table (path layer ABSTAIN,
  `abstain_paths`): dispositions unchanged. The §8 E2E recomputation (measured 0.020) is unaffected — F5 gates no
  episodes at commit.
- Records architecture is clean: DQ is the measurement record (F5 entry present with lineage); the three ship docs
  are disposition records (no disposition moved). Silence ≠ omission; it is the accurate signal.

## (2) Tripwire check — no v2-style tripwire is owed now

- The v2 struck-ledger row (`SHIP_STATUS.md:43`) exists because a live *claim* (general retrieval) needed scoping
  with evidence + sha pins. F5 makes no ship claim — it is a probe-level assertion with no production callers — so
  there is nothing to scope and no bar-miss to strike. A ledger row now would imply a disposition change that did
  not happen.
- The tripwire becomes owed only when (a) call-site wiring lands (then routing/disposition docs must cite the gate),
  or (b) a path-tuning claim is made (then the SHIP §2 path row's "re-baseline before any future path work" clause
  is the slot that must cite F5 as a precondition).

## (3) Minimal accurate note — NOT owed now; draft banked for wiring time (do not apply yet)

- Location if ever needed: `docs/SHIP_STATUS.md` §2, path-layer struck row, appended to the tripwire cell:
  `Future path-tuning claims must additionally pass the F5 STARVED-mass fence
  (DQ:315-321; unwired at commit 9fd75f0 — no tripwire until wiring lands).`
- Location alternative: `docs/PROJECT_ARCHITECTURE.md` §8, one sentence:
  `Delay→STARVED mass trust fence (assert_delay_starved_mass, DQ:315) exists but is unwired — path tuning may not
  cite tuned episodes until a call site enforces it.`
- Neither is owed while caller count is 0; applying either now would document a precondition on work that has not
  started and blur the struck ledger's bar-miss semantics.

Return: **change-needed no — gate is measured in DQ with 0 production callers, so no ship disposition moved and the
three disposition docs stay silent correctly.**
