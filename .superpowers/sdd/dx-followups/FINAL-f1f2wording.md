# FINAL — Task-1 follow-ups F1/F2 wording check (read-only, 2026-11-25)

Worktree: `m0b-t-build` (Verdandi repo). No docs edited, nothing committed, no tests, no Linear.
Definitions: `.superpowers/sdd/dx-full-plan/task-1-review.md:25-26`
(F1 = `ship` vs `—` rendering; F2 = `abstain_rerank` "votable <0.70" phrasing);
carried forward in `.superpowers/sdd/dx-full-plan/final-review.md:95-98`.

## (a) Did W-docs69 (`.superpowers/sdd/dx-followups/W-docs69.md`, commit f01a05b) address F1/F2?

NO. W-docs69's own scope line covers "PRISSUE-69: F13/F17/F19 + void sources"
(W-docs69.md:1) — F1/F2 are Task-1-review findings, a different F-series, and are
never mentioned in the file. Verified via `git show f01a05b --stat`: 5 files —

- `.superpowers/sdd/dx-followups/W-docs69.md` (new, 107 lines)
- `docs/ARCHITECTURE_JEV.md` (0.671 → pre-regen baseline with rerun lineage)
- `docs/PROJECT_ARCHITECTURE.md` (measured test counts + README stale note)
- `docs/PROJECT_REPORT.md` (+3 lines: v6-digest "explicitly unpinned" paragraph, §3)
- `docs/SHIP_STATUS.md` (1 line: v2 manifest file-level sha256 pins + why-not)

The only SHIP_STATUS/PROJECT_REPORT hunks are the v6-digest paragraph and the v2
manifest sha note. Neither the §8 scope table nor the per-component status table
was touched. F1/F2 wording is byte-identical before/after f01a05b.

## (b) Current-doc grep (old vs new wording)

- Old F2 string `while votable`: ZERO hits in `docs/` (was at Task-1 commit bd7b44e:
  `` `abstain_rerank` while votable <0.70 `` — since rewritten, see F2 below).
- `abstain_rerank` in docs now: `PROJECT_REPORT.md:77` (code list), `:126` (scope
  table), `SHIP_STATUS.md:6` (code list), `:21` (status table), `:37` (struck ledger),
  plus `scripts/report_incident.py:37-38` (documents non-emission).
- `—` in SHIP rows: `PROJECT_REPORT.md:125` (Detection SHIP), `:128` (Strong-family
  SHIP (gated)); contrast `SHIP_STATUS.md:19,20,21,24` which use `` `ship` ``.

## (c) Verdicts

### F1 — STILL-OPEN (untouched by W-docs69; inconsistency persists verbatim)

What remains — `docs/PROJECT_REPORT.md:125` and `:128` (§8 scope table):

```
| Detection (retrained frozen sentinel, thr 0.6 + 2-of-3) | SHIP | — | retrieval 0.800 @ clean-fire 0.032, ... |
| Strong-family episodes (breakdown/delay/loss) | SHIP (gated) | — | family top-1 0.752/0.753/0.810, ... |
```

while the §8 narrative directly below (`PROJECT_REPORT.md:135-136`) says
"`ship` marks shipped predictions; all other codes render reason + coverage ...",
and `docs/SHIP_STATUS.md:19,20,24` render the same rows with `` `ship` ``:

```
| Detection (retrained frozen sentinel, thr 0.6 + 2-of-3) | SHIP | `ship` | 0.800 @ clean-fire 0.032, ... |
| Strong families (breakdown/delay/loss) | SHIP gated | `ship` | 0.752/0.753/0.810, ... |
```

Requested fix (unchanged since task-1-review.md:25): normalize the §8 table's two
SHIP rows to `` `ship` ``. One-line-each, docs-only, non-gate-blocking; matters to
Task 7 consumers that match codes verbatim.

### F2 — DONE (but NOT by W-docs69 — resolved incidentally by 86c196b stale-row refresh)

Old (Task-1 commit bd7b44e, now gone — zero `while votable` hits in docs/):

```
`abstain_rerank` while votable <0.70
```

New — `docs/PROJECT_REPORT.md:126` (§8 scope table):

```
| Process attribution (stage-2 LambdaRank, votable) | SHIP (gated) | `abstain_rerank` (ranker struck: V2 max 0.665 <0.70) | rerun votable 0.667 (teacher 0.654, n=2712); calibration-aware + trunc-2 tried, struck after 2 |
```

The semantically confused comparison (votable subset/count vs the ≥0.70 top-1 bar)
is eliminated: the code now predicates on "ranker struck" with the measured max
(V2 0.665 < 0.70, n=2712) as the reason, corroborated by `docs/SHIP_STATUS.md:21`
(`` `ship` / `abstain_rerank` `` + "V1/V2 0.667/0.665 → STRUCK (Task 5), gate ships
without it") and the struck ledger (`SHIP_STATUS.md:37`: bar "votable ≥0.70",
measured "V2 max 0.665 (V1 0.667), n=2712, teacher 0.654"). The review's "define the
real trigger before wiring" is moot-by-strike: `scripts/report_incident.py:37-38`
documents that `abstain_transfer` / `abstain_rerank` are "not produced by this
script (no family model, no transfer slice, no rerank here) -- documented, not
emitted." No verbatim-wiring hazard remains.

Attribution: changed in commit `86c196b` ("docs: refresh stale rows", 2026-11-25),
not in `f01a05b` (W-docs69). `git log -S "while votable" -- docs/PROJECT_REPORT.md`
returns only `86c196b` + `bd7b44e`.

## One-line summary for the lane registry

F1 STILL-OPEN (§8 `—` on 2 SHIP rows); F2 DONE (confused wording gone since 86c196b; W-docs69 touched neither).
