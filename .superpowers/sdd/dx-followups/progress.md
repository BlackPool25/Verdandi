# SDD ledger â€” Shreyas follow-up wave (20 parallel lanes, m0b-t-build @ 86c196b+)

Rulings: (1) user ordered ~20 simultaneous lanes; running 20 background lanes with STRICT disjoint file ownership (map below) â€” any lane finding a scope collision must stop and report instead of overlapping. (2) No Linear comments until PR-ready; no PR without explicit user order. (3) Context7 MCP unavailable â€” SearXNG (tools.searxng.*) + repo docs substitute for all pre-code research. (4) TDD for all behavior changes; RED must fail for the right reason. (5) No AI slop: real behavior, real tests, measured numbers with n/seed/lineage; void sources (PR#31 collision battery, v1 single-origin 0.963) must be flagged never propagated. (6) Compute lanes: low footprint only (<=3 workers, sequential Ollama calls); machine already OOMed at 12-wide.

Ownership map (a file may be WRITTEN by exactly one lane; everyone may READ anything):
- W-gate61: src/diagnose.py gate section, tests/test_*gate* (new), artifacts/calibration.json refit
- W-splits75: scripts/eval_stacked.py split/CV code, split tests, DIAGNOSIS_QUALITY split note
- W-onsetgrid: scripts/eval_localize.py + onset/delay record + tests (READ eval_stacked, never edit)
- W-normfam: NEW analysis script + tests + record (READ eval_stacked, never edit)
- W-f5assert: src/possibility.py or route.py assertion + test + record (use existing artifacts, no battery regen)
- W-shuffle62: scripts/eval_tev.py shuffle mode + run + record (Ollama tev1:4b sequential)
- W-judge72: scripts/eval_jev.py recall top-up + tests (NO model downloads, NO torch installs)
- W-e2e66: NEW scripts/eval_e2e_selective.py + record (existing artifacts/caches only, NO battery gen)
- W-v2naturals74: audit first; rerun ONLY if audit demands, low workers; frozen manifests untouched; NO twin.py edits
- W-docs69: SHIP_STATUS/PROJECT_REPORT/ARCHITECTURE_JEV/PROJECT_ARCHITECTURE corrections ONLY (docs-only)
- FE-1: demo tour roster + tour e2e spec. FE-3: frontend/src/test fixtures enrichment. FE-4: machine-literal dedup across spec files. FE-5: ErrorBoundary.tsx + spec. FE-6: events feed unknown-anomaly surfacing + spec. FE-14: store/ring.ts fail-loud + spec. FE-8: run.sh/demo trap fix. FE-9: sim/*stream* files + ControlsBar drop-count readout. FE-11: StripChart/EventFeed gap rendering.
- Oracle: read-only everything, one report.
Task 11 ship proof + Linear close-out + merge/PR stay with controller after lane reports land.
W-judge72: landed + verified (23 passed) + committed.
W-minors: verified 18 passed, committed. Minor 3 side-table deferred with trigger+DDL (needs diagnose.py owner).
FE-11: verified 25 passed, committed.
W-e2e66: verified 7 passed + JSON summaries; committed script+tests+artifacts. Measured 0.020 struck derived 0.214; docs amended. W-normfam: verified 5 passed; committed script+tests+json+DQ note. W-splits75 F12 note committed with DQ. FE-11: committed. v2naturals rerun in flight; single-node abstain (233/400) is next lever (parked, needs diagnose.py traversing single-node paths — out of lane scopes).
W-v2naturals: rerun overturned Task 3 KEEP -> SCOPE (naturals-ON: ON 0.733 vs OFF 0.694 but cf 0.117>0.093). Docs amended (SIM_BASELINE audit + manifests + SHIP_STATUS + ARCH). 74 needs Linear follow-up comment at PR time (user: no Linear writes until PR-ready). Single-node abstain (58%) = next lever, parked.
W-normfam: complete (063ff6f already carries script+tests+json+DQ); verified 5/5. Remaining open lanes: W-f5assert (test_possibility.py + probe_delay.py), W-shuffle62 (rerun).
Verification sweep: 85 pytest + 78 vitest + tsc clean at HEAD (F5/shuffle excluded, still active). F5 mid-TDD-RED (assert_delay_starved_mass not yet implemented — healthy, hands off). Pending: F5 GREEN+commit, shuffle rerun verdict, W-docs69 F1/F2 wording check, final whole-branch review, Linear PR-time updates (66/74 follow-ups), merge/PR on user order.
W-shuffle62: CLOSED (fixed 0.113 = shuffled 0.113, no position bias, KILL stays; committed aec4cec + 4c07b7b). Only F5 remains active.
W-v2naturals74: CLOSED/verdict FLIPPED to SCOPED (ON 0.733 vs 0.694 BUT cf 0.117>0.093; gaps unpowered), already committed a478def (audit+manifests+SHIP_STATUS:45). Linear 74 needs PR-time flip comment (pending, per no-writes rule). Only F5 remains active.
FINAL-10 (2026-11-25, user-ordered proper close-out; F5 still RED/active, its 3 files off-limits for writes): 1.finalreview 2.lineardrafts 3.docsconsistency 4.dqcomplete 5.testsevidence 6.artifactlineage 7.f1f2wording 8.e2e66check 9.probeassist(readonly) 10.oraclefinal. All report-only, no commits; controller applies fixes after.
FINAL-8 e2e66check: ALL CLEAN (0.020 cited, 0.214 only in struck-context, s0/s1 lineage matches, 6833590 in log).
FINAL-5 testsevidence: python 85/0 (1 skipped), vitest FULL 190/0 (23 files), tsc exit 0. F5 file excluded by design.
FINAL-2 lineardrafts: drafts filed (66 measured-E2E, 74 SCOPED-flip, 13x no-update). Nothing posted (rule stands).
FINAL-9 probeassist: unblocking finding in FINAL-probeassist.md (conservation S<=injected*n + visibility S>=injected-shield gate; C2 delays -> 3-9 C6/C7 STARVED steps). Relay to F5 if still stuck on return.
FINAL-7 f1f2wording: F1 STILL-OPEN (scope-table dashes vs ship wording; queued for controller fix pass), F2 DONE. FINAL-4 dqcomplete: 5 present / 5 missing (F16/F20 gate inputs, F5 pending-active, 66 E2E, 74 naturals, 69 audit). DQ backfill queued for fix pass (numbers in lane reports).
FINAL-10 oraclefinal: GO-WITH-FIXES. 1 blocking (F5 isolation — already planned). 6 non-blocking: DQ paste (66/74/69/F16F20), fullnat manifest sha pins, --natural-breakdowns flag docs, SOLVE_GAPS removal (stale), PR-time Linear comments, parked backlog (Minor-3, Ring wiring, single-node abstain lever). CONFLICT: oracle says F1/F2 fixed, f1f2-lane says F1 STILL-OPEN with quoted lines — controller to adjudicate by reading the file in fix pass.
FINAL-6 lineage: 7/7 verified, 0 mismatched. FINAL-3 docsconsistency: 0 Critical, 21 Minor/7 clusters (M1 routes k; M2/M3 Tev 0.094-vs-0.113 canonical-number question — QUEUED adjudication in fix pass, kill robust either way; M4 stale line pointers; M5 bar typo; M6 stale labels; M7 DQ labels; + sha pins lost). Pending: FINAL-1 review, F5.
FINAL-1 review: CONDITIONAL (C0/I1/M6). Important = a478def dropped f01a05b's F19 sha pins + generator note in SHIP_STATUS + false 'not edited' note in SIM_BASELINE. Minors: 3 justified scope-stretches, 1 transient (HEAD green), Tev 0.094->0.113 lineage note owed, 2 headline-numbers w/o committed artifact. FIX PASS STARTS (docs-only, F5 files untouched).
FIX PASS committed 414ca5f (docs) + 9b0cb0e (2 JSONs). Closed: Important (pins+note), 21 minors (M1/M2/M3/M5/M6/M7/M4+Ep140), F1 ruled NOT-OPEN (dash is Bar-column N/A, disposition SHIP/SHIPS), M5 confirmed typo (DQ:11 source), DQ+4 records, SOLVE_GAPS retired + refs repointed, Minor-6 JSONs committed. Awaiting: F5 GREEN + FINAL re-verify of fix pass.
Docker: dev profile (api-dev:8000 healthy, web-dev:19104 200) + LOCAL_DOCKER.md committed. E2E proven via container: POST /episode validation rejects bad windows, accepts good (seed 7, C2 breakdown), /stream ticks flow. Stack left RUNNING for user testing.
F5-TAKEOVER (user-ordered 20 lanes): 1 implementer (src/possibility.py only) + 18 parallel-safe checkers (own FINAL-f5-* reports, no commits) + reviewer/rerun after IMP lands. Original F5 lane still out there; tests-as-contract decides.
F5-20lane: F5-linear draft filed.
F5-20lane: style review filed — notes file convention (never-raise, non-assert names) CONFLICTS with test contract (raise + assert_ name). RULING: tests win (pinned executable contract); implementer follows tests.
F5-20lane: 19/20 back. Noted: SUMMARY.md:39 F5 line goes stale on GREEN (fix in F5 commit); naming needs-rename overruled (tests pin the name); num hazards = wiring-time only; spec 2/5 synthetic (fence/counterfactual cases, acceptable). Await F5-review.
LEFTOVER-10 (user-authorized Linear posts for 66/74/64; merge NOT authorized — dry-run only): 3 post, 1 verify, wire impl+review, mergeprep, cleanup, docsync, shipdoc.
LEFTOVER-10: PRISSUE-64 follow-up POSTED (872eb152). Awaiting 66/74 posts, verify, wire+review, mergeprep, cleanup, docsync, shipdoc.
LEFTOVER-10: all 3 Linear follow-ups POSTED (64:872eb152, 66:b262d560, 74:f12c4d42). Awaiting verify, wire+review, mergeprep, cleanup, docsync, shipdoc.
LEFTOVER-10: docsync CLEAN (0 issues; DQ record matches committed signature; pointers hold). Awaiting verify, wire+review, mergeprep, cleanup, shipdoc.
LEFTOVER-10: cleanup 0 stray (probe_delay.py = original-lane leftover, expected); shipdoc no-change-needed. Awaiting verify, wire+review, mergeprep.
LEFTOVER-10: HEAD 9fd75f0 GREEN (pytest 94/0 + tsc clean). Awaiting wire+review, mergeprep.
LEFTOVER-10: wire-impl mid-TDD (tests/test_diagnose.py M, RED step; session unmessageable after host restart — DO NOT redispatch; fix loop on return via wirereview CONDITIONAL: new reason code + C1-C5). Mergeprep: target main, 44 ahead, origin/main possibly stale (fetch when authorized); dirty = progress.md + classified untracked only.
LEFTOVER-10: wire committed 76a6d76 (decoupled-delay, 25/110+17 green). All 10 lanes closed.
