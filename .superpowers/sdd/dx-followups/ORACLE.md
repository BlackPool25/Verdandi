# Oracle verdicts — Shreyas follow-up wave (20 lanes), read-only review @ 86c196b+

Scope-note: Shreyas's review text (F16/F20/F12/F9/F21/F17/F5, FE-* XYZ) is NOT in this tree
(grepped worktree + parent repo: no F16/F20/FE-14 hits outside the lane registry itself).
So per-item scope-correctness vs Shreyas's actual words is UNVERIFIABLE from here — plausibility
judged against in-tree counterparts (final-review.md, task-*-review.md). Controller must confirm
the F↔lane mapping below; flags assume the obvious mapping by name.

## (1) Scope-correctness (best-effort; mapping unconfirmed)

| Lane | Presumed target | Verdict |
|---|---|---|
| W-gate61 (τ refit + gate section) | F16 gate item | PLAUSIBLE, with risk: "refit" of served artifacts/calibration.json while W-e2e66 measures against "existing artifacts" = moving baseline. Refit must be additive/versioned or e2e66 must pin. Also τ=0.739 VERIFY already exists (tests/test_calibration_gate.py:175-215); re-prove, don't re-pick silently. |
| W-splits75 (split/CV in eval_stacked) | F20 measurement-hygiene | PLAUSIBLE. Correct file (scripts/eval_stacked.py:212, StratifiedGroupKFold no-shuffle). Must not change composition mid-flight or it invalidates W-gate61/W-e2e66 numbers. |
| W-onsetgrid (eval_localize + onset/delay) | F12 | PLAUSIBLE on READ-only-eval_stacked constraint. |
| W-normfam (NEW analysis script) | F9 | CORRECT SHAPE (new file, no edit of eval_stacked) — best YAGNI-compliant lane here. |
| W-f5assert (assertion in possibility.py OR route.py) | F21 | SCOPE-VAGUE: "or" leaves the write-file undecided at launch. Controller must pick ONE file before launch or two lanes may claim it. Content direction (assert, no regen) is right. |
| W-shuffle62 (shuffle mode + run, Ollama sequential) | 62 shuffle | PLAUSIBLE. Sequential-Ollama + ≤3-worker ruling respected in spec. Watch: shuffle-mode code must be a flag, not a default change, or it perturbs the pinned n=60 tev verdict (0.094 KILL). |
| W-judge72 (recall top-up, no torch/models) | judge item | CORRECT constraint (no downloads) given NLI honestly SKIPPED (final-review §4). Recall-only is the right remainder. |
| W-e2e66 (NEW eval_e2e_selective, caches only) | 66 measured-E2E | CORRECT — directly answers the toy-frame caveat (scripts/report_incident.py:70 uses a +8σ synthetic frame; determinism is genuine per tests/test_report_incident.py:25-59, but it is not measured evidence). New-file + no-regen is the right shape. |
| W-v2naturals74 (audit first, frozen manifests) | v2 naturals | CORRECT — audit-before-rerun + frozen manifests + NO twin.py is exactly the surviving tripwire from final-review §4. |
| W-docs69 (4 named docs only) | 69 void sources + stale rows | PLAUSIBLE but CHECK DUPLICATION: 86c196b already did the stale-row refresh (0.667/tev-0.094/paths-0.072). Docs69 must be scoped to what 86c196b did NOT do (void-source flagging of PR#31/v1-0.963 + task-1-review F5 stale-§7 backlog), else it re-edits the same tables. |
| FE-1/3/4/5/6/14/8/9/11 | FE-1/3/4/5/6/14/8/9/11 | Names match 1:1; no wrong-problem signal visible. FE-5 and FE-14 both already partially exist in-tree (ErrorBoundary.tsx + spec exist; ring store file not confirmed) — lanes should be deltas, not recreations. |

No lane is visibly solving the wrong problem. Two scope hazards (not wrong-problem): W-f5assert file ambiguity; W-docs69 possible overlap with merged 86c196b.

## (2) File-ownership collisions

REAL (must fix before/with launch):
1. Record-file fan-in: W-splits75 names DIAGNOSIS_QUALITY.md; W-onsetgrid / W-normfam / W-f5assert / W-shuffle62 / W-judge72 each say "record"/"note" with NO file. If all five append to DIAGNOSIS_QUALITY.md → 5-way write collision. FIX: assign disjoint record files (or one serialized docs lane).
2. FE-6 vs FE-11: "events feed unknown-anomaly surfacing" vs "StripChart/EventFeed gap rendering" — both plausibly write frontend/src/components/events/EventFeed.tsx (+ spec). Registry does not split MachineEventFeed vs EventFeed. FIX: name the exact file per lane.
3. FE-4 ("machine-literal dedup ACROSS SPEC FILES") vs FE-1/FE-5/FE-6/FE-14 (each owns a spec). FE-4 edits other lanes' files by definition. FIX: FE-4 runs LAST/serialized, or exclude the four owned specs.
4. FE-3 (frontend/src/test fixtures) vs FE-4: fixtures dir (testConstants.ts, synthetic.ts, fixtures/) is shared surface with "dedup across spec files". FIX: state whether src/test/* belongs to FE-3 alone.
5. W-docs69's four named docs vs W-splits75/onsetgrid/normfam/shuffle "records": disjoint ONLY if records stay out of SHIP_STATUS/PROJECT_REPORT/ARCHITECTURE_JEV/PROJECT_ARCHITECTURE. Registry implies this but does not state it. One-line ruling needed.

SEQUENCING (not same-file, but order matters):
6. W-gate61 refits artifacts/calibration.json while W-e2e66 + W-f5assert consume "existing artifacts" → pin or version the artifact, else e2e numbers float mid-flight.
7. W-splits75 editing scripts/eval_stacked.py while W-onsetgrid/W-normfam read it → readers must pin a commit or rebase after splits75 lands.

LOOSE GLOBS (disambiguate): FE-9 "sim/*stream* files" (only TwinStreamProvider.tsx matches today — name it); FE-8 "run.sh/demo trap fix" (one script or two?).

## (3) Slop spot-check (merged work: reporter fallback, gate, report_incident)

GENUINE (not slop):
- Gate wiring: src/diagnose.py:390-406 (T-scaled margin → Platt → τ gate, rank untouched) + behavioral tests (tests/test_calibration_gate.py:92-125 top-1-shift ≤0.01 + abstain path; :175-215 served-τ VERIFY). Real behavior, real tests.
- Template reporter: src/reporter.py:18-47 with hard assert on cited claims (:36); dossier verbatim-copies (:50-64). Minimal, no theater.
- report_incident: scripts/report_incident.py:196-269 + _verify_verbatim (:183-193) + byte-identical determinism tests (tests/test_report_incident.py:25-59). Genuine. Caveat (not slop): +8σ toy frame (:70) means E2E proves plumbing, not performance — W-e2e66 is the correct answer to this.

SLOP / DEAD-CODE HITS:
1. src/phrase.py:185 — `parsed["_latency_s"] = latency` injects a float into the candidate BEFORE phrase()→verify() (:141); verify() digit-diffs the whole candidate (:107-110), so ANY Ollama response with a non-coinciding latency value fails → guaranteed template fallback. The Ollama path is dead code in practice (fail-closed, so safe — but it is theater until fixed). Prior art: final-review.md Minor 2, still present. Owner: NO lane owns src/phrase.py (see §4 gaps).
2. scripts/report_incident.py:178 — bare `except Exception: pass` in decide_packet silently swallows tev failures (via="template" is recorded, which saves it from being silent-behavior, but the error is unlogged — add a reason string).
3. tests/test_phrase.py:47-71 — verify() unit tests are genuine; but there is no test that phrase_with_ollama CAN succeed (a stylist returning clean JSON with the latency key stripped would prove the path is live). Missing-test, not fake-test.

No invented numbers, no fixture-cited-as-evidence, no wrapper-only modules found in the three spot-checked areas.

## (4) Coverage gaps (Shreyas items with no lane — from in-tree review debt)

1. final-review Minor 2 (phrase latency bug): NO lane owns src/phrase.py. Needs a micro-lane (strip _latency_s before verify, add live-path test) — explicitly fix-before-enable, not merge-blocking.
2. final-review Minor 3 (gated incidents leave no store row — audit-trail gap): NO lane owns incidents_store / side-table. Needs a decision: accept invisibility or lane it.
3. Record-file routing (§2.1) is itself a gap: five lanes need a named record target each.
4. Task-1-review F1/F2 (`ship` vs `—` rendering; `abstain_rerank` "votable <0.70" wording): assigned to no named lane — presumably inside W-docs69, but W-docs69's file list covers it only if PROJECT_REPORT §8 table is in scope. Confirm.
5. Task 11 (ship proof: 5×0-diverge re-proof, held-out-seed confirmation, Linear close-out) stays with controller per registry :18 — correctly unassigned, but the held-out-seed reruns have no compute lane if they require new runs (W-v2naturals74 is audit-gated; tuned-point confirmation may need its own run ticket).

## Bottom line for controller

Block launch on: record-file assignments (§2.1), EventFeed split (§2.2), FE-4 serialization (§2.3), f5assert file pick, docs69-vs-86c196b de-dup. Everything else can fly.
