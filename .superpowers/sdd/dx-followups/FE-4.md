# FE-4 — Machine-literal centralization across spec files (PRISSUE-67 nice-to-have)

## Problem
Machine/topology literals (ids `A0`/`B2`/`ASM1`/`SBUF`/`_C7TAIL`, probe steps
`[0,150,299]`, counts 26/28/31, SBUF cap 30 / threshold 24, storeless edge ids,
edge→buffer expectations) were hardcoded and copy-pasted across ~6 spec files —
one topology change would need 6 coordinated edits.

## Fix (pure refactor, zero behavior change)
New shared module `frontend/src/test/testConstants.ts`: single home for all
spec literals (counts, probe steps, special ids, class probes, faceplate ids,
tail-routing probes, roster deltas, edge census, back-edge source, storeless
edge ids, edge→buffer table, labels). SBUF cap/threshold source of truth stays
in `machineMeta` (re-exported so specs import from exactly one place).
6 specs updated to import it, values byte-identical (looped assertions replace
repeated `expect` lines; `toBeNull()` → `toBe(null)` via table, same semantics):
`src/test/topology-layout.spec.ts`, `src/topology/edge-width.spec.ts`,
`src/sim/topology-wiring.spec.ts`, `src/test/panel-equality.spec.ts`,
`src/components/panels/faceplate.spec.ts`, `src/components/panels/lineStats.spec.ts`.
Untouched (other lanes): events feed, diagnosis, ErrorBoundary, store/ring,
run.sh, stream files, StripChart, ControlsBar, tour, fixtures.

## Test proof (green before AND after)
- Before: 6 files 43/43 pass. After: 6 files 43/43 pass (`--maxWorkers=1`).
- `tsc --noEmit`: zero errors in touched files (other lanes' gaps-spec errors remain, not mine).
- Full suite: failures only in other lanes' files (`eventFeed.gaps`,
  `stripChart.gaps`, flaky `ErrorBoundary`) — none in FE-4 scope.
- T12: `scope-grep.mjs` not runnable in this worktree (pre-existing Windows
  drive-prefix path bug, same as FE-5); manual grep of the new module + all 6
  specs for every forbidden token: no matches.

## Status
Done, uncommitted (worktree shared with other lanes — integration left to parent).
