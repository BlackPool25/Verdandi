# FINAL Oracle gate — 20-lane follow-up wave (read-only review @ 9fd0c8e)

Scope: `dfd2839..HEAD` minus F5's still-active files (`tests/test_possibility.py`,
`src/possibility.py`, `probe_delay.py` — untouched by this review).
Method: read-only. No fixes, no commits, no tests run, no Linear touches.
Lane test-count claims below are taken on trust from lane reports + the ledger's
sweep line (85 pytest + 78 vitest + tsc clean at HEAD, F5/shuffle-excluded);
I re-verified every claim that is checkable by reading the tree.

## (1) Interim-findings re-grade (ORACLE.md @ 86c196b+)

| # | Interim finding | Re-grade | Evidence |
|---|---|---|---|
| §2.1 | Record-file 5-way write collision on DIAGNOSIS_QUALITY.md | FIXED | Sections are disjoint in-tree: splits note in Transfer, normfam note in Rerank (§35), shuffle in Tev Criteria-order (§113), onset grid audit (§228), judge template-faithfulness rows. No overwrite observed. |
| §2.2 | FE-6 vs FE-11 both own EventFeed.tsx | FIXED | Committed `EventFeed.tsx` carries BOTH: FE-6 UNKNOWN surfacing (`warnUnknown`, `UNKNOWN_FAMILY`, `feed-unknown` badge) AND FE-11 gap rendering (`interleaveFeedGaps`, `feed-gap` rows). Landed via `3f7161f` + `d6a7a4e` passthrough, no conflict markers, no lost hunk. |
| §2.3 | FE-4 edits other lanes' specs by definition | FIXED | FE-4 was pure refactor (new `testConstants.ts`, 6 specs byte-identical values, 43/43 green before/after). No cross-lane spec edit in tree; full-suite failures cited by lanes are all in other lanes' in-progress files, never FE-4's. |
| §2.4 | FE-3 vs FE-4 `src/test/*` surface overlap | FIXED | FE-3 enriched fixture + new `fixture-steps.spec.ts`; FE-4 centralized literals in the same spec files but values byte-identical. Both committed; suite green per ledger sweep. |
| §2.5 | W-docs69 overlap with merged 86c196b stale-row refresh | FIXED (no duplication) | 86c196b refreshed stale rows (0.667/tev-0.094/paths-0.072); W-docs69 (`f01a05d`) touched only void-source flagging, v6-unpinned statement, manifest sha pins, test-count annotation. Disjoint edits, verified by `git show` file lists. |
| §2.6 | W-gate61 refit moves baseline under W-e2e66 | FIXED by non-event | W-gate61 verdict: CLEAN, no refit. `git log` on `artifacts/calibration.json`: untouched since `080d109` (pre-wave gate commit). No moving baseline; e2e numbers stand on the frozen artifact. |
| §2.7 | W-splits75 mid-flight edit perturbs readers | FIXED | Refactor extracted `_episode_folds` (same sklearn call, same args). No numbers moved, no re-run owed; readers (`eval_localize`, `eval_family_norm`) unaffected. |
| §3.1 | phrase `_latency_s` poison kills Ollama path (Minor 2) | FIXED, verified in tree | `src/phrase.py:108` scrubs `_latency_s` before digit-diff; `:190-198` holds latency in closure, re-attached post-verify. Live-path test exists (mocked urlopen, `path=="llm"`). Committed `42228d4`. |
| §3.2 | `report_incident.py:178` bare `except: pass` | FIXED, verified in tree | Now `except Exception as exc` + stderr log with type+message, then explicit template fallback. Committed. |
| §3.3 | No live Ollama-path test (missing-test) | FIXED | Covered by the W-minors live-path test above. |
| §4.1 | Minor 2 unowned | FIXED | Owned + fixed by W-minors. |
| §4.2 | Minor 3 (abstain leaves no store row) unowned | STILL OPEN, acceptably parked | Confirmed gap; W-minors recorded reopen trigger + DDL sketch, correctly refused dead-code table. Needs a `diagnose.py`-owning lane. Non-blocking (audit-trail, not correctness). |
| §4.3 | F1 (`ship` vs `—`) / F2 (`abstain_rerank` "votable <0.70") wording | BOTH FIXED, verified in tree | PROJECT_REPORT §8 scope table now uses `SHIP (gated)` / `ABSTAIN…` labels, no `—` on SHIP rows; `abstain_rerank` row reads "(ranker struck: V2 max 0.665 <0.70)" — top-1-based, the confused `votable <0.70` phrasing is gone. SHIP_STATUS:21 consistent. |
| §4.4 | W-f5assert "or" file ambiguity | MOOT — F5 still active, hands off | No committed assertion churn in `possibility.py`/`route.py` from the wave (`src/possibility.py` last touched pre-wave `5823dc7`; F5's uncommitted work is `tests/test_possibility.py` +49 only). No collision occurred. |
| §4.5 | Task 11 ship proof (5×0-diverge, held-out-seed, Linear) | STILL OPEN, correctly controller-owned | Held-out-seed reruns need compute tickets; Linear close-out per no-writes rule. Not a merge blocker; IS a ship-claim blocker. |

## (2) New risks introduced by the wave (nothing here fails the merge)

1. **v2 verdict flipped KEEP → SCOPED.** Production-ambient rerun (naturals ON):
   ON 0.733 vs OFF 0.694 BUT cf 0.117 > 0.093 → KEEP fails nominally (both gaps
   within noise: ret z=1.61, cf 95% CI (−0.026,+0.072) — rule is nominal, so it
   fails as written). Docs updated coherently (SIM_BASELINE rerun table :106-138,
   SHIP_STATUS:43, PROJECT_ARCHITECTURE firing bullet). Old breakdown-free KEEP
   (0.719 vs 0.680) correctly superseded-with-lineage, not deleted. **Residual:**
   new `docs/m0b_mass_v2_fullnat_{off,on}.json` manifests have no F19-style sha256
   pins in SHIP_STATUS (pins only cover the old `v2_full` pair) — extend pins.
2. **E2E 0.020 replaces derived 0.214 — single-node rule is the binding constraint.**
   Measured gate-conditional coverage 0.020 pooled (8/400, seeds 0+1), abstain mix
   233 single-node / 72 silent-clean / 87 low-conf. Window-factor arithmetic never
   modeled single-node/path attrition. Struck-with-lineage in SHIP_STATUS:31 +
   PROJECT_REPORT:142-143 (derived line kept struck, not silently deleted — correct).
   **Residuals:** (a) DQ "End-to-end pooled" (§202) still shows only the old
   0.266–0.284 / 0.432–0.436 rows — W-e2e66's DQ insertion text was never applied
   (file-ownership freeze); controller must paste it. (b) Single-node 58% abstain
   is the next lever and needs a `diagnose.py`-traversing lane — parked, out of
   all lane scopes. (c) Selective-acc 0.625 is n=8 noise — docs correctly claim
   no accuracy, coverage only.
3. **Ring fail-loud × gap rendering (FE-11's own honest flag).** Rejected
   non-finite writes leave `0`, indistinguishable from legit 0 readings — so the
   `steps` prop is the ONLY honest gap signal; zero-sniffing deliberately not
   implemented. Badges are opt-in (omitted `steps` = old behavior, zero false
   positives). Safe as merged; live wiring (store-side ingested-step accessor or
   transport `steps` feed) still owed.
4. **`--natural-breakdowns` default-off footgun.** Production ambient is ON;
   regenerating without the flag silently reproduces the breakdown-free battery
   that invalidated the old KEEP. Lane kept default-off to preserve
   `test_battery_v2` 6/6 — acceptable, but the flag's existence + default should
   be documented at the call site or the next regen will repeat the error.
5. **Accepted measurement-hygiene residuals (flagged, unfixed, correctly not snuck in):**
   `finalize_window_model.py:69` every-3rd `eps[2::3]` order-dependent split;
   salted `hash(f)` in `_episode_folds` (`eval_stacked.py:219`) makes exact fold
   assignment vary across processes (stratification holds within a run). Both need
   owner lanes + re-runs; changing either mid-wave would have moved numbers.
6. **F5 RED state in tree.** `tests/test_possibility.py` +49 uncommitted
   (`assert_delay_starved_mass` not yet implemented — healthy TDD-RED per ledger);
   `probe_delay.py` untracked ad-hoc probe; `src/possibility.py` untouched by F5
   (last touch pre-wave). Clean isolation — merge must simply not sweep F5 files.
7. **Hygiene leftovers (non-blocking):** `SOLVE_GAPS.md` is a stale @dfd2839
   snapshot ("SOLVED 0") contradicting current state — delete or re-stamp before
   review, else it will confuse readers. Lane report `.md` files + fullnat
   manifests are untracked (worktree convention; controller decides commit set).
   FINAL-10 close-out lanes (finalreview/lineardrafts/docsconsistency/dqcomplete/
   testsevidence/artifactlineage/f1f2wording/e2e66check/probeassist) are
   report-only with no in-tree artifacts — their outputs live with the controller
   session and are unverifiable from here; I independently re-verified the two
   checkable ones (F1/F2 wording §4.3, E2E numbers §2 above).

## (3) Merge-readiness verdict: GO-WITH-FIXES

No lane solved the wrong problem; no collision materialized; slop items are fixed
and verifiable in-tree; the two verdict flips (v2→SCOPED, E2E→0.020) are measured,
committed, and struck-with-lineage rather than overwritten. The branch is
mergeable subject to the items below.

**Blocking (1):**
1. F5 isolation — merge must exclude `tests/test_possibility.py` (RED),
   `probe_delay.py`, and any `src/possibility.py` churn, OR wait for F5 GREEN.
   Merging the RED test file breaks the suite gate.

**With-fixes, non-blocking (controller applies post-merge or pre-PR):**
2. Paste W-e2e66's DQ insertion (measured selective row + composed pooled row) into
   DIAGNOSIS_QUALITY.md § End-to-end pooled; W-e2e66 text is ready.
3. Extend F19 manifest sha pins to `docs/m0b_mass_v2_fullnat_{off,on}.json`.
4. Document `--natural-breakdowns` default-off at the regen call site (or flip
   default with test updates in an owner lane).
5. Remove or re-stamp stale `SOLVE_GAPS.md` before external review.
6. PR-time Linear follow-ups (per no-writes rule, at PR not now): v2 flip comment
   (74), E2E 0.214-struck comment (66). Ship-claim blockers until posted, not
   merge blockers.
7. Parked follow-ups needing owner lanes (not this merge): Minor-3 side-table
   (`diagnose.py` owner), single-node-abstain lever (58% of E2E mass), every-3rd
   split + salted-hash hardening (with re-runs), gap-signal live wiring
   (store/transport owner), held-out-seed reruns + Task 11 close-out.
