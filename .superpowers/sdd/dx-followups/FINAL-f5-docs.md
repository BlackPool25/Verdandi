# FINAL F5 docs sweep — stale F5 references in docs/

Date: 2026-11-25
Worktree: `C:\Users\athma\OneDrive\Desktop\my projects\Verdandi\.worktrees\m0b-t-build`
Scope: read-only grep of `docs/` (recursive, incl. `docs/demo-evidence/`, `docs/superpowers/`).
Patterns (case-sensitive): `STARVED-mass`, `starved_mass`, `delay.*mass`, `F5`, `possibility gate`.
No edits, no commits, no tests, no Linear.

## Hits

| # | file:line | pattern | text / note | verdict |
|---|-----------|---------|-------------|---------|
| 1 | `docs/demo-evidence/SUMMARY.md:39` | `F5`, `STARVED-mass` | "Still open: F5 delay-STARVED-mass assertion (lane active; excluded from merge until GREEN) …" | **STALE (promissory)** — open-item TODO the F5 lane (`delay_starved_mass` possibility-gate tests) fulfills; line should be retired/updated to GREEN once the lane merges. Single line carries both patterns — counted once. |
| 2 | `docs/m0b_mass_full_manifest.json:1` | `delay.*mass` (regex-span only) | 723 KB single-line manifest; 600× `"class": "delay"` fault rows + distant `"artifacts/m0b_mass_cNN.parquet"` shard paths make the regex span match. No `F5` (0), no `STARVED` (0) in file. | **CURRENT / non-hit** — spurious single-line-spanning match, valid data file, not an F5 reference. Not counted. |

## Zero-hit patterns

- `starved_mass` (snake_case): 0 hits in `docs/`. The five `test_delay_starved_mass_*` names live in `tests/` + `.superpowers/sdd/dx-followups/`, not in `docs/`.
- `possibility gate` (exact phrase): 0 hits in `docs/`. Related `src/possibility.py` references (`DIAGNOSIS_FLOW.md:36,57,101`, `DIAGNOSIS_QUALITY.md:70`) describe implemented behavior (neighborhood, `best_path`) — current, not promissory.
- `docs/superpowers/`: 0 hits for all patterns.

## Explicitly excluded near-misses (not F5-lane references)

- Lowercase `f5c976…` SHA-256 prefixes: `M0B_FREEZE_INPUT.md:35-37`, `SIM_SPEC.md:22-26,610,647-650` — digest pins, current.
- `F-21..F-32` DELAY-class fault IDs, `F13/F19` pins — different identifiers, current.

## Result

- **Stale-hit count: 1** (`docs/demo-evidence/SUMMARY.md:39`).
