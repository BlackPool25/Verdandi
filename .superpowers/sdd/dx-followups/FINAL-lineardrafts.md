# FINAL — Linear follow-up drafts (DRAFTS ONLY — DO NOT POST; no Linear writes per wave rule)

## 1. PRISSUE-66 draft (measured E2E replaces derived)

> PRISSUE-66 follow-up (measured, committed 6833590): episode-level E2E at the served gate (tau=0.739, live `diagnose_incident`) measures pooled coverage **0.020** (8/400, seeds 0+1, n=200/arm), replacing the derived **0.214** (window-transfer, struck as E2E claim). Lineage: `artifacts/e2e-selective-n200-s0.json` + `artifacts/e2e-selective-n200-s1.json` (frozen `m0b_mass` battery, oracle trigger, gate-conditional). Report: `.superpowers/sdd/dx-followups/W-e2e66.md`. Scope unchanged — measurement-only, no ship/scope change.

## 2. PRISSUE-74 draft (v2 verdict flip KEEP → SCOPED)

> PRISSUE-74 follow-up (production-ambient rerun, committed): verdict flips **KEEP → SCOPED**. Naturals-ON rerun (seed 1, 50/300, `--natural-breakdowns`): primary thr-0.7 obs+flow **ON 0.733 vs OFF 0.694 BUT cf 0.117 > 0.093**, so the KEEP condition fails nominally (both gaps within noise: ret z=1.61; cf 95% CI (−0.026,+0.072) — rule is nominal). General 7-family v2 firing claim NOT confirmed under production ambient; win stays quality/loss-only. Paths: `docs/SIM_BASELINE.md` ("W-v2naturals74 rerun results" table), manifests `docs/m0b_mass_v2_fullnat_{off,on}.json`, lane report `.superpowers/sdd/dx-followups/W-v2naturals74.md`. SHIP_STATUS:45 tripwire + PROJECT_ARCHITECTURE firing bullet flagged for revert-to-scoped wording.

## 3. Other 13 assigned issues — no update needed (one line each)

- PRISSUE-61 (W-gate61): CLEAN audit — obs-only confirmed, no refit, `artifacts/calibration.json` byte-identical → no new claim, no update.
- PRISSUE-62 (W-shuffle62): KILL stays — shuffled 0.113 = fixed 0.113, no position-bias rescue → verdict unchanged, no update.
- PRISSUE-63 (W-onsetgrid + W-normfam): confirmatory only — delay re-measured on artifact grid/onset locked, norm-matched gap −0.0128 same sign with family-capped conclusion surviving → no flip, no update.
- PRISSUE-64: no lane in this wave touched that issue's scope and no lane report claims any change under it → nothing to report, no update.
- PRISSUE-65: same as 64 — no wave coverage, no new measurement → no update.
- PRISSUE-67 (FE-3 + FE-4): test-fixture enrichment + spec-literal dedup, no measured backend number changed → no update.
- PRISSUE-68 (FE-5 + FE-6 + FE-14): ErrorBoundary retry / events-feed surfacing / ring fail-loud — UI robustness fixes only, no measured-number change → no update.
- PRISSUE-69 (W-docs69): docs-only audit (void-source grep clean, v6 explicitly unpinned, F19 sha pins) → no verdict change, no update.
- PRISSUE-70: no lane in this wave touched that issue's scope; nothing measured under it → no update.
- PRISSUE-71: same as 70 — no wave coverage, no new measurement → no update.
- PRISSUE-72 (W-judge72): added `claim_recall` + abstain-pairing enforcement; NLI still SKIPPED/deferred with no new citable number → no update.
- PRISSUE-73 (FE-8 + FE-1/FE-9/FE-11 frontend group): run.sh trap fix + tour-roster/drop-counter/gap-rendering — script/UI fixes only, no measured claim changed → no update.
- PRISSUE-75 (W-splits75): PASS — fam-stratified GroupKFold verified, behavior-identical refactor, no numbers moved → no update.
