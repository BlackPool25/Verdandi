# Merge prep — m0b-t-build → main (READ-ONLY, no merge/push performed)

Date: 2026-11-25. Worktree: `.worktrees/m0b-t-build`. No fetch, no commits, no pushes, no PR. No code/docs touched; this report is the only write.

## 1. Current branch + upstream

- Branch: `m0b-t-build` (HEAD `9fd75f0`, 2026-11-25, "feat: delay STARVED-mass gate (F5 GREEN 9/9) + DQ record + wave reports").
- Upstream: `origin/m0b-t-build` (`dfd2839`, 2026-11-10).
- Ahead/behind: `rev-list origin/m0b-t-build..HEAD` = **44 ahead, 0 behind** (merge-base HEAD↔origin/m0b-t-build = `dfd2839` = origin tip, i.e. upstream is a strict ancestor — clean).
- Working tree (dirty): **1 modified** (`.superpowers/sdd/dx-followups/progress.md`, +6 lines, LEFTOVER-10 notes) + **64 untracked** in 6 groups:
  1. `probe_delay.py` (1.8 KB) — F5 probe script.
  2. `docs/m0b_mass_full_manifest.json` (723 KB) — probe input manifest.
  3. `docs/superpowers/plans/2026-11-23-dx-proper-plan.md` (7 KB) — prior-lane plan scratch.
  4. `.superpowers/sdd/dx-full-plan/` (54 files) — prior-lane scratch.
  5. `.superpowers/sdd/dx-proper/` (3 files) — prior-lane research notes.
  6. `.superpowers/sdd/dx-followups/FINAL-left-{verify,cleanup,docsync,shipdoc}.md` (4 files) — sibling lanes landing in parallel (expected; unique filenames, no collision with this file).

## 2. Intended target: `main` (local)

- Evidence: `m0b-t-build` is a feature lane off the long-lived integration branch; `origin/HEAD -> origin/main`; merge-base HEAD↔`main` = merge-base HEAD↔`origin/main` = `270a52d` (same fork point, feature side only).
- Target refs (NO fetch performed per read-only constraint — staleness unknown):
  - Local `main` = `7806e1d` (2026-11-16, "chore: ignore .worktrees"). `git branch -vv` reports it `[origin/main: ahead 4]`.
  - `origin/main` = `42615aa` (2026-11-09, PR #34). 16 days old — **treat as possibly stale**; re-verify with a fetch when authorized.
  - The 4 local-only `main` commits (`origin/main..main` = 4: `7806e1d`, `dd9ff71`, `7c5f288`, `0f9476b`) are sync/chore/local-only docs — no feature overlap expected, but they make the merge a true merge (not FF).

## 3. Scope: log count + diff stat

- `rev-list origin/main..HEAD` = **256**; `rev-list main..HEAD` = **256** (identical: the 4 local-main commits are target-side, they don't change the feature-side count).
- Reverse (target drift HEAD lacks): `HEAD..origin/main` = **5** (PRs #29–#34: window-GBM v1, multi-origin battery, collision-free battery, NAB-lite/metrics/localizers, dense/wide manifests); `HEAD..main` = **9** (those 5 + 4 local).
- `git diff --stat <target>...HEAD` (three-dot, identical totals vs both `main` and `origin/main`): **356 files changed, +131006 / −628**. Bulk: `src/*` + `tests/*` (diagnosis pipeline, gates, calibration, CUSUM, ranker, specialists), `scripts/*` (evals/batteries/trainers), `docs/*` + `artifacts/*` (incl. 6.5 MB `artifacts/stage2-oof.npz`, 7 demo-evidence PNGs), `frontend/*` (diagnosis UI, gap rendering, drop counters), `.superpowers/sdd/dx-followups/*` (lane reports).
- HEAD commit alone (`9fd75f0`): 25 files, +1389/−1 (`src/possibility.py` +34, `tests/test_possibility.py` +49, 20 FINAL-f5-* reports, DQ note, SUMMARY tweak).

## 4. Known blockers (from progress.md + tree state)

1. **Merge NOT authorized.** progress.md:43: "merge NOT authorized — dry-run only"; LEFTOVER-10 still lists verify / wire+review / cleanup / docsync / shipdoc as awaiting. This prep changes nothing about that.
2. **Dirty tree.** `progress.md` (+6) must be committed first. Never `git add -A`: it would sweep groups 3–5 scratch and in-flight sibling files.
3. **Dangling probe lineage (must decide explicitly).** Committed `docs/DIAGNOSIS_QUALITY.md:321` cites `probe_delay.py` + `docs/m0b_mass_full_manifest.json` as probe lineage, but both are UNTRACKED (verified: not ignored, not referenced by any committed test; only that docs line cites them). Handle ONE way before merge: (a) RECOMMENDED — `git add` both (725 KB total, completes the cited lineage); or (b) amend the docs line to drop the citation. Do not merge with the dangling cite unresolved.
4. **F5 original lane.** Takeover GREEN is committed (HEAD: `src/possibility.py`, `tests/test_possibility.py`, 9/9 per DQ record). progress.md:39 notes the original F5 lane is "still out there; tests-as-contract decides". Before merging, confirm no second competing F5 commit landed on this branch; if one did, the committed tests decide.
5. **Scratch must NOT merge.** Groups 3–5 (dx-full-plan 54 files, dx-proper 3 files, 2026-11-23-dx-proper-plan) are prior-lane work products, not part of this branch's history — leave untracked; archive/delete post-merge outside the merge commit.
6. **Sibling lanes + target drift.** FINAL-left verify/cleanup/docsync/shipdoc verdicts are still landing — merge waits for them and any fix commits. Expect manual conflict review against the 9 target-side commits (docs/manifests + windows/metrics areas); re-fetch and re-verify counts when authorized since `origin/main` may be stale.

## 5. Command sequence for the merge (run ONLY once explicitly authorized)

```powershell
# 0. Preconditions (read-only) — run in the worktree
git branch --show-current                          # expect: m0b-t-build
git status -sb                                     # know every M/?? entry; see §1
git rev-list --count origin/main..HEAD             # expect 256 (re-verify after fetch)
git rev-list --count HEAD..main                    # expect 9 + any new target movement
git log --oneline -1 origin/main; git log --oneline -1 main   # note if remote moved

# 1. Refresh refs (ONLY when authorized — this is the first network touch)
git fetch origin

# 2. Finalize the feature tree — EXPLICIT adds only, never `git add -A`
git add .superpowers/sdd/dx-followups/progress.md
git add .superpowers/sdd/dx-followups/FINAL-left-mergeprep.md
# blocker §4.3, option (a) recommended:
git add probe_delay.py docs/m0b_mass_full_manifest.json
# plus any sibling FINAL-left-*.md / fix commits the controller accepts (added by name)
git commit -m "chore: finalize m0b-t-build tree for merge (progress + mergeprep + probe lineage)"
# LEAVE UNTRACKED (do not add): .superpowers/sdd/dx-full-plan/ .superpowers/sdd/dx-proper/
#   docs/superpowers/plans/2026-11-23-dx-proper-plan.md, artifacts/m0b_mass_c*.parquet (ignored)

# 3. Verify the feature tip is green BEFORE merging
python -m pytest -q            # expect 85 passed / 0 failed (+1 skipped); F5 file included post-GREEN
npm --prefix frontend test     # vitest FULL 190/0 (23 files), per FINAL-5 testsevidence
npx --prefix frontend tsc --noEmit   # expect exit 0

# 4. Merge in the MAIN checkout (C:\...\Verdandi), not in the worktree
git checkout main
git pull --ff-only origin main
git merge --no-ff m0b-t-build -m "merge(m0b-t-build): <one-line scope incl. F5 GREEN + 256-commit summary>"
git status -sb; git log --oneline -3; git diff --stat HEAD~1...HEAD | tail -3

# 5. Post-merge verification on `main`, then publish ONLY as authorized
python -m pytest -q; npm --prefix frontend test; npx --prefix frontend tsc --noEmit
git push origin main            # OR: gh pr create --base main --head m0b-t-build (no direct push) — whichever is ordered
```

Readiness: BLOCKED (merge not authorized — dry-run only — plus dirty tree and pending sibling lanes).
