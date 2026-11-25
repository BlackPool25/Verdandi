# FE-1 — Demo tour roster fix (B5 → B2)

## Status: FIXED (uncommitted, shared worktree)

## Root cause
`demo/frontend-tour.mjs` still drove F-21 as `drift@B5`, but B5 was retired
in the 26-machine topology-A roster (`src/config.py` MACHINE_INDEX,
`frontend/src/store/tick.ts` MACHINE_IDS). Consequences, all fatal to the tour:
- `fault-origin` options come from `MACHINES` → `selectOption("B5")` has no
  matching option and times out.
- `validateFaults` rejects unknown origins → the F-21 episode never posts.
- `select-B5` faceplate button no longer rendered (B5 is in neither
  `FACEPLATE_IDS` nor `MACHINE_META`).

## Fix (own files only)
- `demo/frontend-tour.mjs`: all 7 B5 references → B2 (header comment, fault
  comment, `selectOption`, `fault-list`/`episode-faults` asserts, `select-B2`
  click, log label). B2 matches the already-fixed `demo/frontend.sh` digest
  contract (seed 777, drift t0=150 dur=12 mag_sigma 5.2) and `demo/run.sh`,
  and `select-B2` exists as a faceplate probe (`MachinePanel.tsx`).
- `frontend/e2e/tour.spec.ts` (new, owned): static roster guard — asserts every
  machine literal in the tour ∈ 26-machine roster, B5 absent, and the seed-777
  F-21 contract intact. No servers/browser needed.
- No roster/seed fixture needed: the tour self-seeds via `/sim?seed=777` +
  bridge POST, same as `frontend.sh`. No theme/UX changes.

## TDD
- RED: roster check showed `B5 in roster: false`, 7 B5 refs in tour → exit 1.
- GREEN: after fix, 0 B5 refs; `tour.spec.ts` 2/2 pass.

## T12 gates (my files)
- palette-audit: OK (9/177/177, off-palette=0; untouched).
- scope: my files contain zero forbidden tokens (manual grep; `scope-grep.mjs`
  crashes pre-existing on Windows path handling — not mine).
- tsc: no errors in my files. Pre-existing errors remain in other lanes'
  files (`gaps.spec.ts` missing `./gaps`, `feed-gaps.css` missing,
  `lineStats` SBUF_CAP_EXPECT, `panel-equality` FINAL_STEP,
  `stripChart.gaps` props) — untouched per lane ownership.
- vitest: 124 passed; the only failures are the same other-lane files above.
  a11y `reduced-motion` passes.
- Full browser tour (`demo/frontend.sh`) not re-run here: needs owned-port
  bridge+vite and overlaps FE-8/FE-9 lanes; static guard + contract parity
  with `frontend.sh` (B2 digest) is the FE-1 gate.

## Files
- M `demo/frontend-tour.mjs`
- A `frontend/e2e/tour.spec.ts`
