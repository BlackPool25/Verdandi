# M0b Freeze Input: topology-A twin (MINIPRO-33 handoff to MINIPRO-10)

Status: FROZEN at the freeze commit recorded in
`.omo/evidence/task-11-minipro-33-topology-a-reshape.txt` + ledger
`task-11-freeze-pack` entry (SHA recorded post-commit; this doc frozen as-is).
Branch: `shreyasjoshi2511/minipro-33-m01b-topology-a-reshape-shortbranchy-22-machines`.

## Exit criteria (six lines, each with evidence)

1. Machine count N=26 recorded, 22-deviation rationale: dropping to exactly 22
   would erase the process-class injection surface the battery needs, so all
   phenomena stay and the count lands at 26 (18 line + 3 PKG + INSP0 + 4 cell).
   Evidence: `src/config.py` (N_MACHINES=26, N_BUFFERS=26),
   `tests/test_twin_topology_a_config.py`, `docs-battery-topology-A-full182.json`
   (`manifest_rows` 182 = 26x7). Frontend: 28 nodes / 31 edges
   (`frontend/src/topology/nodes.ts` EXPECTED_NODE_COUNT=28,
   `edges.ts` EXPECTED_EDGE_COUNT=31).
2. All 7 fault classes injectable on the 26-machine roster: `build_faults(777)`
   returns 182 rows, `validate_manifest` == [], 7 rep pins (F-21 B2, F-22 A7,
   F-23 C2, F-24 B7P, F-25 B2, F-26 B9, F-06 A0).
   Evidence: `docs-battery-topology-A-full182.json` (`coverage.empty_cells` [],
   `classes_injectable_26_roster` 26 each, `rep_pins` 7).
3. T=300, wall < 600s, 0-diverge preserved on battery `topology-A-full182`:
   wall 1.29s (jobs=12, sequential equiv 15.5s), jobs=1 rerun 6.51s,
   joined digest stable across jobs 1 vs 12, per-seed double-run diverge 0.
   Evidence: `docs-battery-topology-A-full182.json` (`t` 300, `wall_report`,
   `joined_digest`, `joined_digest_stable_jobs1_vs_jobs12` true, `diverge` 0).
4. Duty within T9 tolerances (duty-report GREEN): plant mean over 24 machines
   (standby scope below), natural breakdown on, seeds [777,1234,999,42,2026]:
   RUN 0.850-0.891 (>=0.80), STARVED 0.107-0.138 (<=0.15), BLOCKED 0.000
   (reported, no cap), xfer_open 0, pile-up violations [].
   Evidence: `.omo/evidence/duty-report-topology-A-todo6.json` (status GREEN)
   + battery JSON `duty` block (same numbers, battery_id tagged).
5. Seed-777 re-baselined numbers, schema v2 + battery ID, v1 non-comparable:
   F-21 drift-on-B2 digest `523b0b9e71f47d355cf4e4f4b7f73d29c333747d253d3b016c1edf2957bbd8c4`,
   joined digest `64af2d24a538d2c7c217b8c244835fe230ec902dccbc8632f0e2b1aa8ddf6cb6`,
   quick16 digest `5835f0aef69769c00c59829095dd117be98535141c9cb6bfd4f4ad11e7810616`,
   every number tagged (schema_version=2, battery_id).
   v1 32-machine baselines `962b9c54d022` (flow) and `d2b4fb23` (demo) are
   V1_NON_COMPARABLE, never asserted equal.
   Evidence: `docs-battery-topology-A-full182.json`, golden
   `services/sim_bridge/golden/replay-777-topology-A.json`
   (code_version `twin-2.1.0-topology-A`), fixture
   `frontend/src/test/fixtures/ticks-A-777.json`.
6. Twin FROZEN: no twin tuning after the freeze commit. Any further twin change
   (src/config.py, src/twin.py, goldens, fixtures, battery numbers) needs a
   schema bump (TWIN_SCHEMA 2 -> 3 + new CODE_VERSION + full re-baseline).
   Pin: TWIN_SCHEMA=2, CODE_VERSION=`twin-2.1.0-topology-A`.
   Evidence: this file + freeze commit SHA in the task-11 evidence file +
   ledger; freeze-check `git diff --name-only <freeze-SHA> -- src/ services/
   frontend/ docs-battery-topology-A-full182.json` must stay empty of product
   changes (probe proved it trips, evidence task-11 file).

## Known limits

- Retime values (owner-approved option C, commit 96feb74): AGV_CAP 3,
  TAKT5 single-takt cycles (feed/process/finish/tails/ASM1/ASM2 at 5,
  PKG1/PKG2 at 10; B7S 6, RWK0 8, INSP0 2 frozen), drain grace
  AGV_DRAIN_GRACE=8, standby scope STANDBY_EXCLUDED={B7S,RWK0} so the duty
  mean runs over 24 machines.
- Pile-up bound is a vacuous guard: the Todo 6 failure probe (delay d=6 dur=25
  on A2 at seed 777) never trips it, and the bound as specified (at-cap plus
  downstream-STARVED) is unreachable under deterministic pull. Recorded
  openly, never loosened; see `.omo/evidence/task-6R-bounded-retime.txt`.
- Detector metrics (F1/AC@1/flip/grounding) are MINIPRO-10/M0b owned. The twin
  battery does not produce them and this freeze tunes no thresholds.

## Rebase pointer for MINIPRO-30

SIM_SPEC sections 2-7 amendment + scale-arm appendix landed as commit
`10703ef431570b1cc8b01b0573dc5d01ab487fa8`
(docs(spec): topology-A amendment sections 2-7 + scale-arm appendix).
MINIPRO-30 rebases onto that commit; single-writer note lives in the SIM_SPEC
header. 32-machine config demoted to non-normative scale-arm appendix.

## Unblocks

- MINIPRO-17: unblocked (data acquisition can proceed on the frozen twin).
- MINIPRO-10: freeze input ready (seed-777 baselines above on the frozen twin;
  detector work starts there, not here).
