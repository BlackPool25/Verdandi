# FE-5 — ErrorBoundary Retry: location.reload pattern (PRISSUE-68 Must fix)

## Problem
`ErrorBoundary` Retry button called `this.setState({ hasError: false, error: null })`,
which re-mounted the identical throwing subtree. The boundary re-caught the same
error on the next render — an infinite broken-tree loop with no recovery path.

## Fix
`frontend/src/components/common/ErrorBoundary.tsx`: Retry now does a full page
reload instead of re-rendering in place:

```tsx
onClick={() => window.location.reload()}
```

No `setState` on retry; no style/markup/theme changes (button, class, layout untouched).

## Test proof (TDD: red then green)
`frontend/src/components/common/ErrorBoundary.spec.tsx` — new test
"retry reloads the page instead of re-rendering the identical broken subtree":
renders the fallback via the boundary instance, invokes the Retry `onClick`,
asserts `window.location.reload` called exactly once AND `setState` never called.
- RED before fix: `expected "spy" to be called 1 times, but got 0 times` (reload never fired).
- GREEN after fix: file 3/3 pass; full suite 17 files / 115 tests pass; `tsc --noEmit` clean.
- `palette-audit`: OK (off-palette=0). `scope-grep`: not runnable in this worktree
  (pre-existing Windows `%20`/drive-prefix path bug in `scope-grep.mjs:13`, unrelated);
  manual grep of both touched files for all forbidden tokens: no matches.

## Status
Fixed, uncommitted (worktree shared with other lanes — integration left to parent).
Touched only: `frontend/src/components/common/ErrorBoundary.tsx`,
`frontend/src/components/common/ErrorBoundary.spec.tsx`.
