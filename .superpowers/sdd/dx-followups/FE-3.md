# FE-3 report — tick fixture enrichment (PRISSUE-67 follow-up)

## Result
- Fixture enriched: YES. `frontend/src/test/fixtures/ticks-A-777.json`: 3 rows
  `[0,150,299]` → 12 rows `[0,1,2,149,150,151,152,161,162,163,298,299]`
  (warm-up run, fault-onset run, fault-offset run, tail run).
- Lineage (no hand-written physics): `run_episode(777,
  {id:F-21,class:drift,origin:B2,t0:150,dur:12,mag_sigma:5.2})` with twin
  defaults (`enable_natural_breakdown=True` = bridge POST /episode default);
  rows via `services.sim_bridge.schema.build_tick`, header via `build_header`,
  digest via `replay_digest`; every row `validate_tick`-clean, header
  `validate_header`-clean, double-run digest identical. Dumped with
  `sort_keys=True` (same envelope as before).
- Refresh was REQUIRED, not optional: the committed fixture was
  twin-2.3.0/schema-4 (`d30048ef…`); the worktree twin is twin-2.5.0/schema-6
  (digest `3a1837ec…`), which the live frontend already pins in
  `tickSource.ts`. Mixed-version rows would have been incoherent physics.
  New pins: `code_version twin-2.5.0-topology-A`, `schema_version 6`,
  digest `3a1837ecf28c3c07a11fba62f5e91e553fca11e646104227e6e5c2ab35eee0e1`.
- Step-dependent spec: NEW `frontend/src/test/fixture-steps.spec.ts` (31 tests:
  lineage pins, consecutive-run coverage, frozen shape per row, warm-up /
  onset `FAULT_START@150/B2` / offset `FAULT_END@162/B2` multi-step assertions).
  TDD: RED first (27× `fixture missing step N`), GREEN after enrichment
  (one self-caught fix: twin `part_id` is numeric, not string).
- Specs unblocked: all 6 fixture consumers pass — fixture-steps, panel-equality,
  topology-wiring, lineStats, faceplate, LineHeader (66/66).

## T12 gates (no theme/UX changes; `src/` untouched by this lane)
- palette-audit: OK. scope-grep script: crashes on Windows path handling
  (pre-existing, not mine — verified clean with a Python equivalent of the same
  regex over `frontend/` + `services/`).
- `tsc --noEmit`: 2 errors, both in FE-6/FE-11 files (`EventFeed.tsx`,
  `eventFeed.gaps.spec.tsx`) — other lanes' in-progress work, left alone.
- Full vitest: 186/190; the 4 failures are FE-11 gap specs
  (`eventFeed.gaps`, `stripChart.gaps`) using synthetic events, unrelated to
  the fixture. No commit made (awaiting controller order).

## Repro
`python -c` with the imports above: build `STEPS=[0,1,2,149,150,151,152,161,162,163,298,299]`,
`[S.build_tick(rec,k) for k in STEPS]`, validate each + header, envelope
`{code_version,digest,fault:"F-21-drift-B2",header,schema_version,seed,ticks}`.
