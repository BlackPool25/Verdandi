# FE-9 — SSE drop counter beside row-count readout (DONE)

## What
Dropped SSE tick frames were silent (`streamController` tick handler returned
early on malformed JSON / schema-invalid rows with no count, no notify).
Now counted in the shared transport path and surfaced next to ROWS.

## Changes (FE-9 owned files only)
- `frontend/src/sim/streamController.ts`
  - new `dropCount` field; both silent tick-drop paths (`JSON.parse` throw,
    `parseLiveTick` null) now `dropCount += 1` + `emit()` via the **existing**
    subscriber path (no new subscription, no new render source).
  - reset on episode switch (same block that clears rows/bytes/cursor);
    preserved across disconnect/reconnect resume within an episode.
  - new accessor `droppedFrames(): number`.
  - SSE contract unchanged: single EventSource, `?from_step` resume untouched.
- `frontend/src/sim/tickSource.ts`
  - `TickSource` gains `readonly droppedFrames: number`, wired as
    `ctrl.droppedFrames()` in the returned source object.
- `frontend/src/components/controls/ControlsBar.tsx`
  - reads `ext.source.droppedFrames` during the existing render (no new
    subscription/state) and renders `DROPPED <span data-testid="drop-count">`
    inside the same `ctrl-stat-badge` as ROWS. Standalone (local) mode: 0.
- Specs: `tickSource.lifecycle.spec.ts` +5 tests (`dropped SSE frames (FE-9)`);
  new `ControlsBar.drops.spec.tsx` +2 tests (SSR, no jsdom; stubs `window`
  for `bridgeBase()`).

## TDD
RED: 5x `ctrl.droppedFrames is not a function` + 2x missing `drop-count`
badge (all pre-existing tests still green). GREEN after implementation.

## Test proof
- `tickSource.lifecycle.spec.ts`: 16/16 pass
- `ControlsBar.drops.spec.tsx`: 2/2 pass
- `streamCodec.spec.ts`: 7/7 pass
- T12 `render-counter.spec.ts`: 6/6 pass (0 chrome renders/tick; badges 4-10Hz)
- `tsc --noEmit`: my 5 files clean; 5 remaining errors all in other lanes'
  files (`gaps.spec`, `stripChart.gaps.spec`, `feed.spec`, `panel-equality.spec`)
- full `vitest run`: 157 pass / 33 fail — all 33 in other lanes
  (`fixture-steps` FE-3, `panel-equality` FINAL_STEP, FE-11 gap specs);
  zero in FE-9 scope.
- `palette-audit`: OK. `scope-grep.mjs` not runnable here (pre-existing Win
  path bug: `C:\C:\…` + `%20`); no forbidden tokens added by this change
  (only new identifier is `dropCount`/`droppedFrames`/`DROPPED`).

## Commit
none (worktree shared with 19 other lanes; my 5 files + 1 new spec left
uncommitted — see `git status` for `frontend/src/sim/stream*`,
`ControlsBar.tsx`, `ControlsBar.drops.spec.tsx`).
Note: `topology-wiring.spec.ts` shows unrelated churn from another lane;
untouched by FE-9.
