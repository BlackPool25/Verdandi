# F5 merge-isolation guard (read-only rule task, no code changes)

Worktree: `C:\Users\athma\OneDrive\Desktop\my projects\Verdandi\.worktrees\m0b-t-build`
Captured: 2026-11-25 (UTC) via `git status --short`, `git ls-files`, `git diff`.

## 1. `git status --short` current dirty files (F5 scope relevant)

Full output at capture time:

```text
M .superpowers/sdd/dx-followups/progress.md
M tests/test_possibility.py
?? .superpowers/sdd/dx-full-plan/
?? .superpowers/sdd/dx-proper/
?? docs/m0b_mass_full_manifest.json
?? docs/superpowers/plans/2026-11-23-dx-proper-plan.md
?? probe_delay.py
```

F5 scope subset:

```text
M tests/test_possibility.py        # TRACKED + modified (49 insertions per git diff --stat)
?? probe_delay.py                  # UNTRACKED
src/possibility.py                 # CLEAN (absent from status, absent from git diff --name-only)
```

Non-F5 dirty files (do NOT merge with F5):

```text
M .superpowers/sdd/dx-followups/progress.md
?? .superpowers/sdd/dx-full-plan/
?? .superpowers/sdd/dx-proper/
?? docs/m0b_mass_full_manifest.json
?? docs/superpowers/plans/2026-11-23-dx-proper-plan.md
```

Supporting evidence:

```text
$ git diff --name-only
.superpowers/sdd/dx-followups/progress.md
tests/test_possibility.py
# -> src/possibility.py NOT present = clean
```

## 2. `src/possibility.py` is TRACKED — whole-file exclusion is IMPOSSIBLE

```text
$ git ls-files src/possibility.py tests/test_possibility.py probe_delay.py
src/possibility.py
tests/test_possibility.py
# -> probe_delay.py absent = UNTRACKED; src/possibility.py present = TRACKED
```

```text
$ git diff --stat src/possibility.py
(empty — 0 hunks at capture time; file clean)
```

Rule (additive-only-diff):

- NEVER exclude/ignore/overwrite the whole `src/possibility.py` file on merge.
- F5 merge may carry ONLY the new-function hunk(s) in `src/possibility.py`.
- Acceptance check: `git diff src/possibility.py` must show only the new function addition + no other hunks (no edits, no reformatting, no deletions elsewhere).
- If `git diff src/possibility.py` shows any hunk outside the new function, REJECT the merge and re-isolate.

## 3. Exclude-if-red set (exact)

If red/broken at merge time, EXCLUDE these from the F5 merge (leave them behind, do not block `src/possibility.py` hunk):

```text
tests/test_possibility.py
probe_delay.py
```

- `tests/test_possibility.py`: TRACKED + currently modified; excludable per-hunk/file on red.
- `probe_delay.py`: UNTRACKED helper/probe; excludable by simply not `git add`-ing it on red.
- `src/possibility.py`: NOT excludable whole-file (TRACKED core file) — only the additive-only-diff rule above applies.

## Verify command (one line, PowerShell-safe, read-only)

```powershell
git status --short; git ls-files --error-unmatch src/possibility.py; git diff --stat; git diff -- src/possibility.py
```

Expected GREEN for F5 merge:

- `git status --short` shows F5 files only (plus known non-F5 files listed above, which must be left out of the merge).
- `git ls-files --error-unmatch src/possibility.py` exits 0 (proves TRACKED).
- `git diff --stat` shows `src/possibility.py` with insertions only for the new function.
- `git diff -- src/possibility.py` shows only the new-function hunk, zero other hunks.

Task constraints honored: no edits, no commits, no tests, no Linear — this file is the only write.
