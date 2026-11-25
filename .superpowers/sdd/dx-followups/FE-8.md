# FE-8 — run.sh trap unbound-var fix (PRISSUE-73)

## Status: FIXED (uncommitted — left for lane integration; worktree holds other lanes' changes)

## Problem
`run.sh` ran under `set -euo pipefail` with `cleanup() { kill "$BRIDGE_PID" "$WEB_PID" 2>/dev/null; }`
and `trap cleanup EXIT`, but neither PID was initialized at the top. Any first-run failure that
exits after the trap is registered but before both PIDs are assigned fired the trap into unbound
variables, appending trap noise after the real diagnostic:
- bridge fails to start (line-43 `exit 1`): `WEB_PID` never assigned → `WEB_PID: unbound variable`.

(Prereq failures at lines 25–31 exit before `trap` registration, so they were already clean.)

## Fix (`run.sh` only — no other files touched)
1. Initialized both PIDs beside the other defaults: `BRIDGE_PID=""` / `WEB_PID=""`.
2. Guarded cleanup with default-expansion + non-empty checks, mirroring the already-correct
   `demo/frontend.sh` pattern (which needed no change — verified read-only):
   ```bash
   cleanup() {
     [ -n "${BRIDGE_PID:-}" ] && kill "${BRIDGE_PID:-}" 2>/dev/null || true
     [ -n "${WEB_PID:-}" ] && kill "${WEB_PID:-}" 2>/dev/null || true
   }
   ```
   The trailing `|| true` also preserves the exit code under `set -e` when the PIDs are stale.
   `demo/run.sh` has no trap/background PIDs — nothing to fix there (read-only check).

## Verification (no full demo boot; harness loads the ACTUAL init+cleanup/trap lines from run.sh)
Harness: `fe8-verify.sh` (in %TEMP%/fe8bin, outside repo) evals the real `set`/init lines and the
real `cleanup()`+`trap` range from a given run.sh, then simulates three states under `set -u`.

| file | fail-early (no PIDs) | fail-bridge (only BRIDGE_PID) | happy (both, dead pids) |
|---|---|---|---|
| fixed `run.sh` | rc=1, diagnostic only, stderr empty | rc=1, diagnostic only, stderr empty | rc=0, stderr empty |
| `HEAD:run.sh` (orig) | rc=1 + `BRIDGE_PID: unbound variable` | rc=1 + `WEB_PID: unbound variable` | **rc=1** (trap clobbered exit 0) |

- `bash -n run.sh` syntax OK; `run.sh --help` output unchanged, rc=0 (help exits pre-trap; arg parsing untouched).
- Side benefit confirmed by the matrix: the old trap also turned a clean happy-path `exit 0` into
  rc=1 when both PIDs were stale; the fix preserves rc=0. Stdout on the happy path is untouched
  (kill list identical when both PIDs are set).

## Commit
None — worktree contains other lanes' in-progress changes; `git diff -- run.sh` is exactly the
hunk above. Ready for the owning lane to stage/commit.
