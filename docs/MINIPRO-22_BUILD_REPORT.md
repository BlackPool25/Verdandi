# MINIPRO-22 Build Report — CH8 Current + CH9 Energy (C1-C2)

## 1. Objective

MINIPRO-22 (Linear M0.2b CH8 current + CH9 energy, C1-C2) on the topology-A
26-machine twin.

Branch lineage: `origin/main 2854f03` through work branch
`athmabhiram/minipro-22-verify-fixes` (12 commits, HEAD `29914fd`; report
content written at `f3378a2`, committed as `29914fd`). Single golden re-baseline for the deliberate schema 2 to 3 break.
Linear issue MINIPRO-22 updated via comment `bb23d104`, left In Progress
(NOT closed) pending owner sign-off.

## 2. What was built

### W1 — `src/config.py` CURRENT tables (commit `97a87b9`)

- `I_RATED_BY_CLASS`: 9 classes (feed / form / process / finish /
  inspect-tail / assembly-kit / assembly-join / test / rework). Values are
  marked assumptions pending owner sign-off.
- `K_BY_GROUP`: A/B 1.0, C 0.7, ASM/PKG/INSP 0.5, RWK 0.3.
- `I_IDLE_RATIO = 0.15`, `STEP_SECONDS = 1`, `VOLT = 400`.
- `resolve_current()`: resolves per-machine `I_rated` + `k`; raises on
  unknown prefix; per-machine override raises in v1 (not supported).

### W2 — Dedicated eta streams (commit `a845808`)

- `children[idx].spawn(1)[0]` per machine; `N_STREAMS == 36` literal and
  `spawn(36)` literal untouched; retired 26-31 assert untouched.
- `(26, 300)` episode-start pre-draw, approximately 1-2 ms class warm
  (median ~1.7 ms over 7 repeats, range 1.3-2.3 ms; ~18 ms cold
  first-touch including numpy init; single `standard_normal` site).
- Noise spec (verify-fix, commit `f3378a2`): stored eta rows are
  `N(0, 0.05 * I_rated)` per-row scaled via `ETA_SIGMA_RATIO = 0.05`.
  Audit-caught gap: pre-fix rows were flat `N(0, 1)`.

### W3 — CH8 in-step hook at 5 sites (commit `fae40e4`)

- Formula: `I = I_idle + k * L * (I_rated - I_idle) + eta[idx][t]`,
  clamped `max(0, I)`.
- `L = 1` iff RUN-cycling (held or `tput == 1`); `L = 0` otherwise.
- BLOCKED-holding / STARVED / DOWN draw `I_idle`; `DOWN == I_idle` lock
  per owner decision (repair-de-energized ruled OUT for v1).
- `record["currents"]` is 26x300 float64; never obs-derived (non-collinear
  by design; val-derived current forbidden).

### W4 — CH9 header-only energy (commit `ec0c8f3`)

- `flow_stats["energy"] = {sum_kVAh, per_unit, note, unit: "kVAh-apparent",
  step_seconds: 1}`.
- `E_step = sqrt(3) * 400 * I_clamped * STEP / 3600`; relative-only index,
  no power factor, no RNG.
- `packaged == 0` implies `per_unit None` with note `packaged==0`.
- Scrubbed from digest (`energy` in scrub set); no per-tick CH9 series.

### W5 — Bridge schema v3 (commit `6369123`)

- `TICK_KEYS + ("currents",)` with range check on the currents row.
- Header carries the energy dict verbatim.
- `TWIN_SCHEMA 2 -> 3`, `SCHEMA_VERSION 3`,
  `CODE_VERSION twin-2.2.0-ch8ch9`.
- Temperature / unknown-key rejection kept; v2 records non-comparable
  (deliberate break, one re-baseline).

### W6 — Determinism + calibration checklist (commit `e746089`)

- 0-diverge x5 seeds 777 / 1234 / 999 / 42 / 2026.
- `docs/CALIBRATION_CHECKLIST.md`: relative-index warning + `q_det_digest` /
  `q_det_wall` helpers; threshold VALUES stay in MINIPRO-10/17, never in
  the twin.

### W7 — Single golden regen + Linear (commits `d847f00`, `31340c4`)

- One schema-v3 golden re-baseline with inventory (commit `d847f00`).
- Linear MINIPRO-22 progress comment `bb23d104` (commit `31340c4`);
  issue NOT closed.

### Verify-fixes (commits `25471b0`, `f045f45`, `f3378a2`)

- `25471b0`: one stale-comment fix (eta-hook comment).
- `f045f45`: ruff clean (`I001` / `FURB136` / `RUF059` / `PLR0402` + format).
- `f3378a2`: CH8 eta scaled to `N(0, 0.05 * I_rated)` per Linear noise
  spec via row scaling + re-baseline.

## 3. Commit history (`git log --oneline origin/main..HEAD`)

| # | SHA | Subject | Group |
|---|-----|---------|-------|
| 1 | `97a87b9` | feat(twin): add CURRENT tables + STEP_SECONDS | W1 |
| 2 | `a845808` | feat(twin): dedicated CH8 eta streams vectorized | W2 |
| 3 | `fae40e4` | feat(twin): CH8 in-step currents 26x300 | W3 |
| 4 | `ec0c8f3` | feat(twin): CH9 header-only energy scrubbed | W4 |
| 5 | `6369123` | feat(bridge): TICK currents + header energy v3 | W5 |
| 6 | `e746089` | test(twin): determinism wall calibration checklist | W6 |
| 7 | `d847f00` | chore(twin): re-baseline schema v3 goldens | W7 |
| 8 | `31340c4` | docs(linear): MINIPRO-22 progress | W7 |
| 9 | `25471b0` | docs(twin): fix stale eta-hook comment | fix |
| 10 | `f045f45` | fix(lint): ruff check+format clean (I001/FURB136/RUF059/PLR0402) | fix |
| 11 | `f3378a2` | fix(twin): scale CH8 eta to N(0,0.05·I_rated) per Linear + re-baseline | fix |
| 12 | `29914fd` | docs(minipro-22): add CH8/CH9 build report with results | report |

Subjects above are as recorded by `git log --oneline origin/main..HEAD`
in the worktree (rows 1-11 written at `f3378a2`; row 12 is this report's
own commit).

## 4. Results

| Check | Result |
|-------|--------|
| pytest ch8 (7) + ch9 (5) + bridge-schema (16) + split-census (6) | 34 passed |
| diverge filter (`-k "diverge and (777 or 1234 or 999 or 42 or 2026)"`) | 10 passed |
| `check_replay --seed 777` | PASS (300 ticks, resume-150 identical, digest `0280680a39d0c712a6d494931a92f66cabee04946681fa2bb98bb398ec9c4d34`) |
| `ruff check` | clean |
| `ruff format --check` | 22/22 |
| `mypy src/` | clean |
| F1 plan compliance audit | APPROVE |
| F2 code quality review | APPROVE (0 blockers) |
| F3 real manual QA | APPROVE |
| F4 scope fidelity | APPROVE |
| Momus plan audit | OKAY |

## 5. Documented divergences from Linear text (deliberate, locked)

- **G1, `w_m` CUT (causality):** the Linear formula term `+0.6*w_m` is
  stale and was cut for v1. Past-only wear only in a future design.
- **G2, `sqrt(3)` kVAh-apparent vs Linear `I*400*dt`:** CH9 ships as a
  relative-only apparent-energy index. No power factor. Linear text
  amended as stale.
- **G3, dedicated `spawn(1)` vs machine-stream draws:** Linear
  machine-stream interleaving rejected (breaks 0-diverge). Shipped
  `children[idx].spawn(1)[0]` with 0-diverge proven x5.
- **G4, `I_idle = 0.15` rule-of-thumb + `DOWN == I_idle`:** owner-locked
  for v1; repair-de-energized ruled out. Example amps stay assumptions.
- **G5, schema 2 to 3 breaking with one re-baseline:** `currents` added to
  ticks, energy to header. v2 records non-comparable by design.

## 6. Accepted items and pending gates

Accepted:

- Wall +2% FAIL accepted. The 2% band on ~0.11 s episodes is
  noise-dominated on this machine (breaching seed rotates run-to-run;
  post-warmup probe 0.106-0.118 s for all five seeds, all inside budget).
  Vectorized Ziggurat pre-draw + stream isolation kept; monitor in staging.
- `Q_DET` helper + checklist sufficient. Threshold values stay in
  MINIPRO-10/17; none added to the twin.

Pending (block merge):

- Owner sign-off on the `I_rated` / `K` assumption tables and on PKG/INSP
  `k`.
- Linear stays In Progress until that sign-off lands.

## 7. Repro commands

Run from the worktree root (as recorded in build ledger):

```powershell
$env:GIT_MASTER='1'; pytest tests/test_ch8_current.py tests/test_ch9_energy.py services/sim_bridge/tests/test_schema.py tests/test_twin_split_census_topology_a.py
$env:GIT_MASTER='1'; pytest -k "diverge and (777 or 1234 or 999 or 42 or 2026)"
$env:GIT_MASTER='1'; python services/sim_bridge/scripts/check_replay.py --seed 777
$env:GIT_MASTER='1'; ruff check src/ tests/
$env:GIT_MASTER='1'; ruff format --check src/ tests/
$env:GIT_MASTER='1'; mypy src/
$env:GIT_MASTER='1'; git log --oneline origin/main..HEAD
```

Bare `ruff check .` / `ruff format --check .` are NOT green at repo scope
(53 pre-existing errors / 14 files outside `src/ tests/`); the verified
gate scope is `src/ tests/` only.
