# FINAL follow-up-wave review — delta 86c196b..9fd0c8e (24 commits)

Scope: read-only. Follow-up wave delta only; base-plan verdict (CONDITIONAL, docs-only) not re-litigated.
F5-active files (tests/test_possibility.py, src/possibility.py, probe_delay.py): untouched by every wave commit — confirmed via per-commit name lists. No fixes applied, no tests run, no Linear writes, no other files written.

## Method

Per-commit stat + full diff reviewed for all 24 commits. Numbers spot-checked against committed artifacts (e2e-selective JSONs, eval_family_norm.json, fullnat manifests) and re-derived arithmetically where closed-form (v2naturals CIs/z/MDE all reproduce). No twin.py / services / schema / SSE-transport / theme-token edits found in the delta. F5 exclusion honored throughout.

## Findings

### Critical: 0

- No UI/theme breakage: only additive scoped CSS (new gaps.css/feed-gaps.css; appended classes in events.css); no palette/token/variable edits; no TwinStreamProvider or tick-path subscription changes.
- No invented verdict-moving numbers; no safety/authority changes; no F5-file contact.

### Important: 1

1. **Cross-lane overwrite with evidence loss (a478def vs f01a05b).** f01a05b (W-docs69) added file-level sha256 pins for the v2 manifests to the SHIP_STATUS v2 row (F19 fix). a478def (W-v2naturals74) rewrote that same row for the KEEP→SCOPED flip and dropped the pins plus the "generator emits none" note — the committed F19 fix is silently reverted in the current tree (pins recomputable from committed manifests, but absent from docs). SHIP_STATUS.md / PROJECT_ARCHITECTURE.md are W-docs69-owned per the registry, yet written by three wave commits (f01a05b, 6833590, a478def). Compounding: a478def's own SIM_BASELINE note claims SHIP_STATUS was "not edited by this lane" while the same commit edits it. Owed: pins restored beside the scoped row; note corrected.

### Minor: 6

1. **Scope stretch, no collision (da1fa67, W-judge72):** touched src/faithfulness.py (claim_recall + aggregate field), outside its registry set (eval_jev.py + tests). Functionally required, tested, unowned by any other lane.
2. **Adjacent-lane DQ write (063ff6f, W-normfam):** added the DQ split-integrity note (F12), which is W-splits75 record territory. No conflict; content consistent with d36f0e8.
3. **Adjacent-file touch (1d00e41, W-onsetgrid):** fixed the wrong-grid bug in scripts/bench_windows.py (outside its named files, but the bug lived there) plus a Windows resource-guard drive-by in the same file. Justified, tested.
4. **Transient broken intermediate (3f7161f, FE-6):** imports ../charts/gaps, which only landed in e14798e (FE-11) ~2.5 min later — 3f7161f alone does not typecheck. HEAD green per sweep; commit-hygiene only.
5. **Unexplained 1-episode drift (aec4cec, W-shuffle62):** fixed arm 0.113 (6/53) vs Task-4 baseline 0.094 (5/53) under claimed-identical seed=0 episode set (inter-arm identity verified; vs-baseline drift not addressed). Verdict-robust (both << 0.671, KILL stays); lineage note owed.
6. **Headline numbers without committed machine-readable artifact:** shuffle62 (logs gitignored) and onset-grid delay table (window_cache gitignored) — recomputable via committed scripts + committed battery/manifests, same posture as base tev, but below the artifacts-JSON bar the rest of the wave met. FE-4 testConstants additionally broadens two assertions (AGV_TAILS adds B9; NEVER_DIVERTS adds B1/C1) — strengthening, reported green at HEAD; noted only.

## Not verified (not findings)

- Test-green claims rely on the reported sweep (85 pytest + 78 vitest + tsc); running tests was out of scope for this review.
- Wall-clock/p99 envelopes: no timing harness in wave; unchanged from base declined-to-judge.

## Verdict: CONDITIONAL

Conditions (docs-only, minutes): (1) restore the F19 sha256 pins beside the scoped v2 row in SHIP_STATUS.md (recompute to confirm); (2) correct the false "not edited by this lane" note in SIM_BASELINE.md. No code rework. Counts: **Critical 0 / Important 1 / Minor 6**.
