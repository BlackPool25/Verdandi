# FINAL docs-consistency audit — follow-up wave numbers (read-only)

Date: 2026-11-25. Worktree: `m0b-t-build`. Scope: cross-check every MEASURED
number cited in `docs/PROJECT_REPORT.md`, `docs/PROJECT_ARCHITECTURE.md`,
`docs/SHIP_STATUS.md`, `docs/SIM_BASELINE.md`, `docs/DIAGNOSIS_QUALITY.md`
against lane sources (`.superpowers/sdd/dx-followups/W-*.md`) and manifest
JSONs (`docs/m0b_*.json`, `artifacts/*.json`). No fixes applied (read-only).

## Verdict

- **Critical (decision-changing): 0.** Every ship/abstain disposition rests on
  numbers that match their sources: E2E 0.020, v2 SCOPE flip, tau=0.739,
  norm gap −0.0128, battery ON/OFF tables, rerank V1/V2, paths 0.072/0.287.
- **Minor (cosmetic/stale): 21** line-level items, grouped in 7 clusters
  below. Kill/ship verdicts are robust to all of them.

## Sources verified CONSISTENT (no mismatch — recorded so nobody re-audits)

- **E2E selective:** `PROJECT_REPORT.md:142` and `SHIP_STATUS.md:31` match
  `W-e2e66.md:37-41` exactly (pooled 0.020 = 8/400, acc 0.625 = 5/8;
  s0 0.015@0.333, s1 0.025@0.800; abstain 233/72/87) and both artifact
  summaries (`artifacts/e2e-selective-n200-s0.json:2222-2235`,
  `-s1.json:2222-2234`; grep confirms covered:true 3/5, correct:true 1/4).
  Derived 0.214 struck everywhere it appears (`PROJECT_REPORT.md:143`,
  `SHIP_STATUS.md:31,62`); no live citation of 0.214 anywhere.
- **v2 SCOPED flip:** `SIM_BASELINE.md:112-138` table (ON obs+flow 0.733 =
  513/700 @ cf 0.117 = 35/300 vs OFF obs-only 0.694 = 486/700 @ 0.093 =
  28/300) matches `PROJECT_ARCHITECTURE.md:52` and `SHIP_STATUS.md:43`
  exactly. Breakdown-free KEEP (0.719 vs 0.680) labeled superseded in all
  three places. Focused +0.185 (0.815−0.630) consistent.
- **Calibration gate:** tau=0.739, T=2.58, ECE 0.246→0.034, NLL 2.465→1.366,
  VERIFY risk 0.044 (0.0442656 in `verify-calibration.json:21-26`,
  `calibration.json:24-32`), transfer row 0.327/0.739/0.337@0.300 n=8945,
  exclude-held 0.490/0.413 (`ranker-calibration.json:132-143`) — consistent
  across `PROJECT_REPORT.md:41,112,127`, `SHIP_STATUS.md:22-23,57`,
  `PROJECT_ARCHITECTURE.md:45-46,74`, `DIAGNOSIS_QUALITY.md:164-200,260-279`,
  `W-gate61.md:62-66`.
- **Norm gap:** −0.0128 both norms (`DIAGNOSIS_QUALITY.md:47-48` =
  0.7645−0.7773 from `artifacts/eval_family_norm.json:263-314`), all six
  per-family attributions round-trip to the JSON. Matches `W-normfam.md:34-47`.
- **Rerank V1/V2** (0.667/0.665, teacher 0.654, n=2712) and **paths**
  (0.072/0.287, teleport Δ+0, n=167) consistent everywhere except mean-k (M1).
- **Detection** 0.800/0.032 and 0.759/0.017 consistent (`DIAGNOSIS_QUALITY.md:10-11`
  vs `PROJECT_REPORT.md:32,125`, `SHIP_STATUS.md:19-20`).

## Mismatches (all Minor)

### M1. Routes mean-k: three values for one metric
- `docs/PROJECT_REPORT.md:36` cites mean-k **1.1** vs source
  `docs/DIAGNOSIS_QUALITY.md:77-78` (Task 5 lane record) mean-k **1.8**.
  (`docs/SIM_BASELINE.md:27,211-212` carry a third value, 1.5, on the old
  battery.) Root-hit/subseq columns agree (0.072/0.287); only mean-k
  disagrees. Verdict "diagnostic-only stands" unaffected.

### M2. Tev machine top-1 cited as 0.094 (5/53); latest lane rerun is 0.113 (6/53)
Source: `.superpowers/sdd/dx-followups/W-shuffle62.md:4-7` fixed arm 0.113
(6/53), recorded at `docs/DIAGNOSIS_QUALITY.md:120`. Stale citations:
- `docs/PROJECT_REPORT.md:132` — machine 0.094 (5/53)
- `docs/SHIP_STATUS.md:27` — machine 0.094 (5/53)
- `docs/SHIP_STATUS.md:39` — 0.094 machine (5/53)
- `docs/SHIP_STATUS.md:58` — struck as decider (0.094)
- `docs/PROJECT_ARCHITECTURE.md:53` — machine 0.094 (5/53)
- `docs/PROJECT_ARCHITECTURE.md:74` — tev 0.094 STRUCK
Family 0.132 citations are current (fixed-arm value). Kill disposition is
robust (0.113 still << 0.3 bar and << 0.671 teacher) → Minor, not Critical.

### M3. DIAGNOSIS_QUALITY internal: 0.094 vs 0.113 for same protocol
- `docs/DIAGNOSIS_QUALITY.md:101,108-109` (Task 4: 0.094, 5/53, seed=0) vs
  `docs/DIAGNOSIS_QUALITY.md:120,123` (shuffle fixed arm: 0.113, 6/53,
  seed=0, episode set claimed identical per `W-shuffle62.md:24-25`).
  5/53 → 6/53 move is unreconciled (model nondeterminism? loader-change
  side effect?). Kill verdict robust either way → Minor provenance gap.

### M4. Stale cross-doc line pointers (lane edits shifted lines; values correct)
- `docs/SHIP_STATUS.md:22` → `DIAGNOSIS_QUALITY.md:48-53`; actual
  calibration section is `DIAGNOSIS_QUALITY.md:260-265`.
- `docs/SHIP_STATUS.md:23` → `DIAGNOSIS_QUALITY.md:56-65`; actual transfer
  table is `DIAGNOSIS_QUALITY.md:268-272`.
- `docs/PROJECT_REPORT.md:128-129` → `DIAGNOSIS_QUALITY.md:40-43` for family
  top-1; actual family typing is `DIAGNOSIS_QUALITY.md:215-218` (40-43 is
  now the norm-matched table).
- `docs/PROJECT_REPORT.md:130` → `DIAGNOSIS_QUALITY.md:56-65` for transfer;
  actual is `DIAGNOSIS_QUALITY.md:268-272`.
- `docs/PROJECT_REPORT.md:84` (§5 65-B evidence), `:105` (§6 sensor stack),
  `docs/SHIP_STATUS.md:28` → `SIM_BASELINE.md:107-113` for the sensor-stack
  0.033–0.067 program; the sensor-stack section now lives at
  `SIM_BASELINE.md:215-221` (107-113 is the fullnat rerun table).

### M5. Detection bar typo (10x)
- `docs/PROJECT_REPORT.md:32` bar column reads "≥0.75 @ **≤0.5**" vs source
  `docs/DIAGNOSIS_QUALITY.md:10` bar "≥0.75 @ **≤0.05**". Measured 0.032
  passes either; verdict unaffected → Minor.

### M6. SIM_BASELINE dated snapshots read as current
- `docs/SIM_BASELINE.md:27` (11-10 handoff: rerank **0.685** votable, paths
  0.132) asserts "unchanged by sim work", but the 11-25 battery regen moved
  rerank to 0.667 (`DIAGNOSIS_QUALITY.md:23`) and the ranked arm to 0.072.
  Origin of 0.685 itself is unprovinced (differs from both 0.673 original
  and 0.667 rerun). Ship tables elsewhere use current numbers → Minor.
- `docs/SIM_BASELINE.md:210-213` (Routes 11-11: ranker evidence **0.162**)
  carries no in-section stale label; the stale marking lives only in
  `DIAGNOSIS_QUALITY.md:73-74,81`. → Minor.

### M7. Pre-regen rerank rows retained unlabeled beside rerun rows
- `docs/DIAGNOSIS_QUALITY.md:20-22` (0.673/0.671/0.455–0.456, n=2665) have no
  pre-regen/date label while `docs/DIAGNOSIS_QUALITY.md:23-25` are labeled
  "RERUN 2026-11-25" (n=2712) — a reader can mistake 0.673 as current.
  `PROJECT_REPORT.md:33` cites the rerun values correctly. → Minor.

### Ancillary lineage note (not counted above)
- `W-docs69.md:95-99` pinned file-level sha256 for
  `docs/m0b_mass_v2_full_{off,on}.json` into SHIP_STATUS; current
  `docs/SHIP_STATUS.md` contains no sha256 (grep-confirmed) — the pin was
  lost in a later rewrite. Manifests themselves exist and grid-identity was
  lane-verified (`W-v2naturals74.md:22-24`); fullnat manifests
  `docs/m0b_mass_v2_fullnat_{off,on}.json` exist as cited. → Minor
  provenance erosion, no number affected.

## Lineage index used
Lane reports: `W-e2e66`, `W-v2naturals74`, `W-shuffle62`, `W-normfam`,
`W-gate61`, `W-docs69`, `W-splits75`, `W-onsetgrid`, `W-judge72`.
Manifests/artifacts: `docs/m0b_mass_v2_full{,_nat}_{off,on}.json` (present),
`artifacts/e2e-selective-n200-s{0,1}.json` (summaries match),
`artifacts/calibration.json`, `artifacts/verify-calibration.json`,
`artifacts/ranker-calibration.json`, `artifacts/eval_family_norm.json`
(all match cited values to rounding).
