# W-v2naturals74 report — full-mix OFF/ON audit (Shreyas F2/F13 on PRISSUE-74)

Date: 2026-11-25. Worktree: `m0b-t-build`. No frozen-manifest or `src/twin.py` edits.
Audit record: `docs/SIM_BASELINE.md` ("W-v2naturals74 audit" section).

## 1. Natural breakdowns ON (production)? FAIL
- `scripts/gen_mass_battery.py` hardcoded `enable_natural_breakdown=False` (line 135 pre-lane);
  both arms generated breakdown-free. `export_v6` default is True; the script overrode it.
- Production = naturals ON (`M0B_FREEZE_INPUT:29`, `TEST_CASES:241`, `SIM_SPEC:184`).
- Breakdown fault family in the grid = injected faults, not ambient MTTF/MTTR. Manifests record
  no ambient flag (provenance gap, flagged not fixed).

## 2. Clean-fire power, n=300/arm? FAIL — limit stated
- Eval reproduced exactly on existing caches (all 8 rows match). Exact counts:
  clean-fire ON 19/300=0.063 vs OFF 24/300=0.080: Δ=-0.0167, SE=0.0210,
  95% CI (-0.058,+0.025) incl. 0; MDE@80%≈0.059 ≫ 0.017.
- Retrieval ON 503/700 vs OFF 476/700: Δ=+0.0386, SE=0.0245, z=1.57, p≈0.12 two-sided,
  95% CI (-0.009,+0.087) incl. 0. (Prior "≈2.2σ" used single-arm SE; two-sample z≈1.6.)
- Sign consistent 4/4 ON-vs-OFF comparisons — suggestive, not powered. Powering Δcf=0.017
  needs ~4300 clean/arm: infeasible. KEEP rule = nominal non-inferiority read, recorded as such.

## 3. Gain knobs frozen per protocol E? PASS
- Row diff OFF↔ON ignoring `extra`: 0. `extra` diffs exactly 200 = 100 loss `couple_loss`
  + 100 quality `sink_all`. Grids, seeds (1), mag/sev/dur/t0 identical. Nothing else moved.

## Rerun: YES (completed)
- Demanded by (1); both arms (grid-identity forces the pair), seed 1, same 50/300 density.
- Added `--natural-breakdowns` passthrough to existing `scripts/gen_mass_battery.py`
  (default off; `tests/test_battery_v2.py` 6/6 green — defaults preserved).
- NEW paths only: `docs/m0b_mass_v2_fullnat_{off,on}.json`,
  `artifacts/m0b_mass_v2_fullnat_{off,on}_*.parquet`, `artifacts/cache_v2_fullnat_{off,on}`.
  Rerun fixes ambient, not (2)'s power limit (stands by arithmetic).

## Verdict / SHIP_STATUS — FLIPPED to SCOPE (production-ambient rerun)
- Primary (thr 0.7, obs+flow ON vs obs-only OFF): 0.733 > 0.694 BUT cf 0.117 > 0.093
  → KEEP condition NOT met nominally. thr-0.5 passes; same-tag readings pass both tags.
  Both gaps within noise (ret z=1.61; cf 95% CI (-0.026,+0.072)), but the rule is nominal.
- General (7-family) v2 firing claim NOT confirmed under production ambient → SCOPE to
  quality/loss-only. Focused precedent untouched. Full table in `docs/SIM_BASELINE.md`.
- SHIP_STATUS:45 + PROJECT_ARCHITECTURE firing bullet need revert to scoped wording —
  FLAGGED for W-docs69/controller (not edited by this lane). Nothing committed.
