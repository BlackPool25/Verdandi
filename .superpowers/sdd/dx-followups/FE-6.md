# FE-6 — Events feed unknown-anomaly surfacing (PRISSUE-68 Must fix)

## Status: FIXED (uncommitted — tree is red from other lanes, see Gates)

## Problem
Two silent `try/catch` hides the anomaly class the feed exists to surface:
- `feed.ts` `filterEvents`: `classifyEvent` throw → `return false` (unknowns vanish under a family filter with zero trace).
- `EventFeed.tsx` `FeedRow`: throw → `familyAttr = "UNKNOWN"` with no warn, no count, badge class `evt-badge-unknown` unstyled (renders as OK-adjacent neutral).

## Fix (TDD: RED 12/12 missing-export → GREEN 12/12)
- `frontend/src/components/events/feed.ts`
  - `UNKNOWN_FAMILY`, `familyOf()` (never throws), `isUnknownEvent()`, `countUnknown()`, `unknownNames()`.
  - `warnUnknown(events, scope)`: `console.warn` once per fresh unknown name (`event-feed[scope]: N row(s) with unknown family (...) — rendered as explicit ! UNKNOWN, never as OK`); returns unknown count; quiet when clean. `resetFeedWarnings()` test hook.
  - `filterEvents`: `family: "UNKNOWN"` isolates unknowns; known families exclude without throwing; no filter keeps all (never silently dropped).
  - `labelFor`: unknown → `"... ! UNKNOWN"` (glyph convention, color never alone).
  - `summarizeFeedAnomalies(all, visible, overflow)` → `{total, visible, overflow, unknownCount, unknownNames, countMismatch}`; `countMismatch = visible+overflow !== total`.
- `frontend/src/components/events/EventFeed.tsx` (FeedRow catch deleted): `warnUnknown` per rows-computation, header `data-testid="feed-unknown"` (`! N unknown (names)`) and `data-testid="feed-mismatch"` badges, UNKNOWN in family select, row `row-unknown` + `! UNKNOWN` glyph (`data-testid="event-unknown-glyph"`).
- `frontend/src/components/events/events.css`: `row-unknown` / `evt-badge-unknown` / badge styles (reused `#b13e53/#fae4e8/#7f2737` hues, no new palette).
- `frontend/src/components/events/feed.spec.ts`: 12 tests (all above behaviors).

## Dossier coordination (shape only, no dossier rewrite)
Dossier lane may embed `FeedAnomalySummary` verbatim (import from `../events/feed`). Suggested optional field: `feedAnomalies?: FeedAnomalySummary | null` on `DiagnosisDossier` + render `unknownCount`/`unknownNames`/`countMismatch` next to nodes/paths. Not implemented here per ownership.

## Test proof
- `npx vitest run src/components/events/feed.spec.ts src/components/events/anomaly.spec.ts` → **37/37 pass** (12 new + 25 existing).
- Full `npx vitest run`: 173 pass / 17 fail — all 17 in other lanes' files (`fixture-steps` FE-3; `eventFeed.gaps` + `stripChart.gaps` FE-11 RED specs for unimplemented `steps`/gap rows). Zero failures in FE-6 files.
- `npx tsc --noEmit`: no errors in FE-6 files; remaining errors all in FE-11 (`steps` prop, `./gaps`) / FE-3 / panel-equality files.
- `palette-audit`: OK. Scope tokens: manual grep clean on all 4 touched files (repo `scope-grep.mjs` itself crashes on Windows path `%20`/drive-letter bug — pre-existing, environmental, fails before reading any file).
- Anomaly-spec forbidden-token self-test still passes (no `score/pcmci/narrat/replay_digest/temperature/detector` substrings added).

## Collisions / notes for controller
- FE-11 owns EventFeed gap rendering; I touched only FeedRow catch + header badges + select option in `EventFeed.tsx` (no list/cap logic). Their `eventFeed.gaps.spec.tsx` failures are their unimplemented feature, not my regression (failure output shows my UNKNOWN option rendering fine alongside).
- No commit: tree red from other lanes' mid-work specs; committing FE-6 alone is possible but left to controller. Files touched: `feed.ts`, `EventFeed.tsx`, `events.css`, `feed.spec.ts` (new).
