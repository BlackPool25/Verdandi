# Contribution: MINIPRO-22 CH8 Motor Current + CH9 Energy-per-Unit (Topology-A Twin, Schema v3)

## Summary

Implements MINIPRO-22 (CH8 motor current + CH9 energy-per-unit) on the topology-A 26-machine twin with bridge schema v3.

Contributor branch `athmabhiram/minipro-22-verify-fixes` vs `origin/main 2854f03`. HEAD at write time `fa9f74b` (13 commits in range). One deliberate schema 2 to 3 break with a single golden re-baseline. No root `CONTRIBUTING.md` exists in the worktree; this `docs/` record is the deliverable.

## Scope

CH8 in-step currents (26x300) plus CH9 header-only energy on topology-A twin, bridge TICK currents plus header energy, schema v3, determinism proof, calibration checklist, build report, golden regen. Out of scope: per-tick CH9 series, power factor, repair-de-energized DOWN state, threshold values in the twin.

## What was added (new files)

| File | Purpose |
|------|---------|
| `tests/test_ch8_current.py` | CH8 current tests (7 tests) |
| `tests/test_ch9_energy.py` | CH9 energy tests (5 tests) |
| `tests/test_twin_w6_determinism_wall.py` | Determinism wall / 0-diverge x5 seeds |
| `docs/CALIBRATION_CHECKLIST.md` | Relative-index warning plus `q_det_digest` / `q_det_wall` helpers |
| `docs/MINIPRO-22_BUILD_REPORT.md` | Verified build report with results |
| `services/sim_bridge/golden/replay-777-topology-A.json` | Regenerated schema-v3 golden (only golden touched in `git diff origin/main..HEAD --stat`) |

## What was edited (modified files)

| File | Change |
|------|--------|
| `src/config.py` | CURRENT tables (`I_RATED_BY_CLASS`, `K_BY_GROUP`, `I_IDLE_RATIO`) plus `STEP_SECONDS`, `VOLT`, `resolve_current()`, schema 3 |
| `src/twin.py` | Dedicated eta streams, CH8 in-step hook at 5 sites, CH9 header energy, digest scrub, `ETA_SIGMA_RATIO = 0.05` (`N(0, 0.05 * I_rated)`) |
| `services/sim_bridge/schema.py` | v3 TICK currents plus range check, header energy verbatim, `TWIN_SCHEMA` 2 to 3 |
| `services/sim_bridge/sse.py` | Schema v3 currents / energy passthrough |
| `services/sim_bridge/app.py` | Schema v3 version bump (`CODE_VERSION twin-2.2.0-ch8ch9`) |
| `services/sim_bridge/tests/test_schema.py` | v2 to v3 pins (16 tests) |
| `services/sim_bridge/tests/test_replay.py` | Golden digest pin update |
| `services/sim_bridge/scripts/check_replay.py` | Seed-777 replay check update |
| `scripts/check_gates.py` | Gate update for schema v3 |
| `tests/test_twin_battery_topology_a.py` | Record-keys / schema pin update |
| `tests/test_twin_flow.py` | Record-keys / schema pin update |
| `tests/test_twin_fork_failover.py` | Record-keys / schema pin update |
| `tests/test_twin_gates.py` | Record-keys / schema pin update |
| `tests/test_twin_schema.py` | v2 to v3 pin update |
| `tests/test_twin_split_census_topology_a.py` | Split-census pin update (6 tests) |
| `tests/test_twin_topology_a_config.py` | Config pin update |
| Lint / format / comment fixes | Stale eta-hook comment fix, ruff `I001` / `FURB136` / `RUF059` / `PLR0402` plus format, CH8 eta noise scaling fix plus re-baseline |

## Test results (exact, from `docs/MINIPRO-22_BUILD_REPORT.md`)

| Check | Result |
|-------|--------|
| pytest ch8 (7) + ch9 (5) + bridge-schema (16) + split-census (6) | 34 passed |
| diverge filter x5 seeds (777 / 1234 / 999 / 42 / 2026) | 10 passed |
| `check_replay --seed 777` | PASS, 300 ticks, resume-150 identical, digest `0280680a` |
| `ruff check src/ tests/` | clean |
| `ruff format --check src/ tests/` | 22/22 |
| `mypy src/` | clean |
| Determinism wall +2% | HONEST FAIL, accepted by owner (2% band on ~0.11 s episodes is noise-dominated on this machine; breaching seed rotates run-to-run; post-warmup probe 0.106-0.118 s for all five seeds, all inside budget) |

Note: bare `ruff check .` / `ruff format --check .` are NOT green at repo scope (53 pre-existing errors / 14 files outside `src/ tests/`); verified gate scope is `src/ tests/` only.

## How a reviewer verifies

Run from the worktree root:

```powershell
$env:GIT_MASTER='1'; pytest tests/test_ch8_current.py tests/test_ch9_energy.py services/sim_bridge/tests/test_schema.py tests/test_twin_split_census_topology_a.py
$env:GIT_MASTER='1'; pytest -k "diverge and (777 or 1234 or 999 or 42 or 2026)"
$env:GIT_MASTER='1'; python services/sim_bridge/scripts/check_replay.py --seed 777
$env:GIT_MASTER='1'; ruff check src/ tests/
$env:GIT_MASTER='1'; ruff format --check src/ tests/
$env:GIT_MASTER='1'; mypy src/
$env:GIT_MASTER='1'; git log --oneline origin/main..HEAD
```

Expected outputs: 34 passed; 10 passed; `PASS (300 ticks, resume-150 identical, digest 0280680a...)`; ruff check clean; `22/22`; mypy clean; 13-commit log from `origin/main 2854f03` to HEAD.

## Outstanding merge-blockers

- Owner sign-off on the `I_rated` / `K` assumption tables and on PKG/INSP `k`.
- Linear MINIPRO-22 stays In Progress until that sign-off lands.
