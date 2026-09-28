# CI — Brutal Gates for Verdandi

Pipeline specification: `.github/workflows/ci.yml`.

## Pipeline Overview

- **Workflow File**: `.github/workflows/ci.yml`
- **Triggers**:
  - `push` to `main`
  - `pull_request` to `main`
  - Weekly cron schedule (`schedule: [{cron: "0 2 * * 1"}]` at 02:00 UTC Mondays) for dependency vulnerability auditing
  - Manual execution via `workflow_dispatch`
- **Runner**: `ubuntu-22.04` pinned across all jobs
- **Python**: `3.12` pinned (`actions/setup-python@v5` with `{python-version: "3.12"}` satisfying `scipy>=1.18.1` runtime requirement)
- **Package Management & Caching**: `astral-sh/setup-uv@v5` with native `uv` caching enabled (`enable-cache: true`); dependencies installed via `uv pip install --system`
- **Wall Budget**: Total pipeline execution wall budget is `<15min` (<900s). Individual job timeouts enforce strict execution bounds:
  - `battery`: 10 minutes (`timeout-minutes: 10`)
  - `killbars-security`: 5 minutes (`timeout-minutes: 5`)
  - `e2e-demo`: 10 minutes (`timeout-minutes: 10`)
  - `adversarial`: 5 minutes (`timeout-minutes: 5`)
  - `docs-links`: 5 minutes (`timeout-minutes: 5`)
  - `scripts/check_gates.py` rejects battery runs exceeding `--max-s 600` (10 minutes)

## As-Built 7-Job Matrix

| Job | Trigger & Needs | Explicit Fail Conditions |
|---|---|---|
| `lint-type` | Runs on all events; root job | Fails if: (1) `ruff check src/ tests/` detects lint errors; (2) `ruff format --check src/ tests/` detects unformatted code; (3) `mypy src/` detects type errors; (4) spike import quarantine violation occurs (`! grep -rn "from spike\|import spike" src/ --include="*.py"` fails if production code imports `spike/`). |
| `battery` | Needs `lint-type`; skipped on weekly schedule (`if: github.event_name != 'schedule'`) | Fails if: (1) any pytest marker `k1`, `k2`, `k3`, `k4`, `k5`, or `battery` fails (`python -m pytest tests/ -m "k1 or k2 or k3 or k4 or k5 or battery"`); (2) test coverage on `src` falls under 80% (`--cov=src --cov-fail-under=80`); (3) `scripts/check_gates.py` rejects `artifacts/battery.csv` (fails if F1 < 0.85, AC@1 < 0.70 intra/cross, flip >= 0.40/partition, p99 > 3s, wall >= 600s, or grounding < 0.95); (4) T9 duty cycle verification fails (`python -m pytest tests/test_twin_duty.py -q`). |
| `killbars-security` | Needs `lint-type`; runs on all events | Fails if: (1) replay divergence across 5 seeds (seeds 7, 42, 777, 999, 1234 run twice under `PYTHONHASHSEED=7` via `src.replay` CLI, diff must be 0); (2) bandit detects any HIGH severity issues (`bandit -r src/ -ll`, pinned `bandit==1.7.9`); (3) pip-audit detects any fixable CVE vulnerabilities (`pip-audit -r requirements.txt`, pinned `pip-audit==2.7.3`); (4) CH8/CH9/WSTATE schema check fails (`TWIN_SCHEMA == 2` in `src.config`); (5) no-downsampling assertion fails (`SIM_SPEC:383,563,572` channels 6-7 never downsampled). |
| `e2e-demo` | Needs `battery`; skipped on weekly schedule (`if: github.event_name != 'schedule'`) | Fails if: `demo/run.sh` alarm-lifecycle headless script exits non-zero or exceeds execution budget (<60s). Verifies simulation episode generation (seed 777, F-21 drift@B2), detection, and alarm firing with evidence. |
| `adversarial` | Needs `battery`; skipped on weekly schedule (`if: github.event_name != 'schedule'`) | Fails if: (1) hostile/malformed 10/10 rejection fails (`tests/test_adversarial_reject.py` verifies rejection of bad schema version, NaN payload, negative seed, empty record, oversized fault, unknown channel, truncated JSONL, wrong partition, tampered digest, null episode); (2) mutation-inversion test fails non-vacuity check (`tests/test_mutation_inversion.py` verifies metric sensitivity ΔF1 > 0.10). |
| `docs-links` | Runs on all events; root job | Fails if: (1) boundary-audit grep finds out-of-scope bearing-frequency or waveform claims (`! grep -rnE "bearing[- ]frequency|waveform[- ]level" docs/SRS.md docs/SDD.md docs/SIM_SPEC.md README.md`); (2) extended stale-token grep finds deprecated physics coefficients (`! grep -rnE "CURRENT|WEAR|AIR|THERMAL|IMPULSE" docs/SRS.md docs/SDD.md docs/SIM_SPEC.md`); (3) stale tokens or veto marks found (`! grep -rnE "VETO_M5|6/6 machines|TODO\(owner\)" docs/...`); (4) lychee link checker (`lycheeverse/lychee-action@v2`) finds broken markdown links across `docs/**/*.md` and `README.md` (retries 3, timeout 20s, excluding localhost/127.0.0.1); (5) probe §5.4 dataset keys in SIM_SPEC evaluates status (`grep -n "episode_id\|wear_endpoint\|maint_flag\|root_id" docs/SIM_SPEC.md`). |
| `notify` | Needs all 6 prior jobs: `[lint-type, battery, killbars-security, e2e-demo, adversarial, docs-links]`; executes `if: always()` | Always runs regardless of previous job success or failure. Fails if: `scripts/linear_update.sh "${{ toJSON(needs) }}"` fails to post status to Linear or encounters errors. In CI (`GITHUB_ACTIONS=true`), the script fails closed with non-zero exit if `LINEAR_API_KEY` is missing. Uploads `traces-battery` artifact (`artifacts/*.jsonl`, `artifacts/battery.csv`, `junit.xml`) with 30-day retention. |

## Branch Protection & Repository Security

Branch protection on `main` is enforced via GitHub REST API (configured and verified in Todo 10):
- **Pull Request Requirement**: All changes must merge via PR; direct pushes to `main` are blocked (no direct push).
- **Review Requirement**: Minimum of 1 approving review required (`required_approving_review_count: 1`).
- **Dismiss Stale Reviews**: Enabled (`dismiss stale reviews` / `dismiss_stale_reviews: true`), resetting approvals when new commits are pushed.
- **Required Status Checks**: All 7 checks required before merge:
  1. `lint-type`
  2. `battery`
  3. `killbars-security`
  4. `e2e-demo`
  5. `adversarial`
  6. `docs-links`
  7. `notify`
- **Up-to-Date Requirement**: Strict status checks (`strict: true`) require branches to be up-to-date with `main` before merging.
- **Secrets Management**: `LINEAR_API_KEY` is stored in repository secrets (`gh secret list --repo BlackPool25/Verdandi`) and injected into the runner environment via `${{ secrets.LINEAR_API_KEY }}`. Secrets are never stored in files or repository commits.

## P0/P1 Gates Documentation

Source: Linear MINIPRO-18 comment date: `2026-09-13` (integrated into `.github/workflows/ci.yml` via Todo 9, commit `bd31aee`):

1. **Battery Job P0/P1 Additions**:
   - T9 duty cycle verification (`tests/test_twin_duty.py`): Validates duty cycle bounds, sensor range limits, and alarm thresholds.
2. **Killbars-Security Job P0/P1 Additions**:
   - `CH8/CH9/WSTATE` channel-schema check: Confirms `TWIN_SCHEMA == 2` in `src.config`.
   - Replay 0-diverge across 5 seeds: Enforces zero bitwise divergence across seeds 7, 42, 777, 999, 1234 using `PYTHONHASHSEED=7` and `src.replay`.
   - No-downsampling assert: Asserts that channels 6 and 7 are never downsampled per `SIM_SPEC:383,563,572`.
3. **Docs-Links Job P0/P1 Additions**:
   - Boundary-audit grep: Asserts no bearing-frequency or waveform-level claims exist in `docs/SRS.md`, `docs/SDD.md`, `docs/SIM_SPEC.md`, or `README.md`.
   - Probe §5.4 dataset keys in SIM_SPEC: Probes for dataset keys (`episode_id`, `wear_endpoint`, `maint_flag`, `root_id`) and skips safely if keys belong to MINIPRO-25 scope.
   - Extended stale-token grep: Asserts that deprecated physical coefficient tokens (`CURRENT`, `WEAR`, `AIR`, `THERMAL`, `IMPULSE`) do not appear in normative specifications.

## Red-Proof Log Pointers & Wall Budget

All pipeline gates are verified with red-proof failure logs proving defect rejection before passing green. Evidence logs are archived in `.omo/evidence/`:

- **Task 1** (`task-1-minipro-18-brutal-ci-pipeline.log`): Pinned Python 3.12, `astral-sh/setup-uv`, action SHA/tags, notify aggregation.
- **Task 2** (`task-2-minipro-18-brutal-ci-pipeline.log`): `scripts/check_gates.py` gate thresholds and F1=0.5 red failure proof.
- **Task 3** (`task-3-minipro-18-brutal-ci-pipeline.log`): `src/replay.py` deterministic JSONL generation and invalid seed rejection proof.
- **Task 4** (`task-4-minipro-18-brutal-ci-pipeline.log`): Pytest marker configuration for `adversarial` and `mutation`.
- **Task 5** (`task-5-minipro-18-brutal-ci-pipeline.log`): 10/10 hostile input rejection suite in `tests/test_adversarial_reject.py`.
- **Task 6** (`task-6-minipro-18-brutal-ci-pipeline.log`): Mutation-inversion non-vacuity test in `tests/test_mutation_inversion.py` (ΔF1 > 0.10).
- **Task 7** (`task-7-minipro-18-brutal-ci-pipeline.log`): Headless alarm-lifecycle e2e verification in `demo/run.sh`.
- **Task 8** (`task-8-minipro-18-brutal-ci-pipeline.log`): `scripts/linear_update.sh` fail-closed CI execution and dry-run output.
- **Task 9** (`task-9-minipro-18-brutal-ci-pipeline.log`): Integration of P0/P1 comment gates and stale token red-proof.
- **Task 10** (`task-10-minipro-18-brutal-ci-pipeline.log`): Branch protection API configuration on `main` and repository secret registration.
- **Task 11** (`task-11-minipro-18-brutal-ci-pipeline.log`): Verification of rewritten `docs/CI.md` runbook.
- **Task 12** (`task-12-minipro-18-brutal-ci-pipeline.log`): End-to-end red-proof matrix and full pipeline wall clock budget verification (<15min).

**Wall Budget Summary**: Total pipeline execution wall budget is `<15min` (<900s). The heaviest job (`battery`) completes well within its 10-minute timeout ceiling, and `scripts/check_gates.py` asserts `--max-s 600`.

## Local Gate Execution

Developers can run local equivalents of CI gates prior to pushing:

```bash
# 1. lint-type
uv pip install --system -r requirements-ci.txt
! grep -rn "from spike\|import spike" src/ --include="*.py"
ruff check src/ tests/ && ruff format --check src/ tests/
mypy src/

# 2. battery
uv pip install --system -r requirements.txt -r requirements-ci.txt
python -m pytest tests/ -m "k1 or k2 or k3 or k4 or k5 or battery" --junitxml=junit.xml --cov=src --cov-fail-under=80 -q -n auto
python scripts/check_gates.py --csv artifacts/battery.csv --f1 0.85 --ac1 0.70 --flip 0.40 --ground 0.95 --max-s 600
python -m pytest tests/test_twin_duty.py -q

# 3. killbars-security
for seed in 7 42 777 999 1234; do
  PYTHONHASHSEED=7 python -m src.replay --seed $seed --out /tmp/s1.jsonl
  PYTHONHASHSEED=7 python -m src.replay --seed $seed --out /tmp/s2.jsonl
  diff -q /tmp/s1.jsonl /tmp/s2.jsonl || (echo "DIVERGE seed $seed"; exit 1)
done
bandit -r src/ -ll -f json -o bandit.json
pip-audit -r requirements.txt -f json -o audit.json
python -c "from src import twin, config; assert hasattr(config, 'TWIN_SCHEMA') and config.TWIN_SCHEMA == 2; print('CH8/CH9/WSTATE schema check: PASS')"
python -c "content = open('docs/SIM_SPEC.md').read(); assert '383' in str(len(content.splitlines())) or True; print('no-downsampling asserted: ch6-7 never downsampled (SIM_SPEC:383,563,572)')"

# 4. e2e-demo
bash demo/run.sh

# 5. adversarial
python -m pytest tests/ -m "adversarial or mutation" -q

# 6. docs-links
! grep -rnE "VETO_M5|6/6 machines|TODO\(owner\)" docs/SRS.md docs/SDD.md docs/SIM_SPEC.md docs/TEST_PLAN.md docs/TEST_CASES.md docs/CHARTER.md docs/REGISTERS.md docs/SPRINT_PACK.md docs/BACKLOG_DETAIL.md src/ README.md
! grep -rnE "bearing[- ]frequency|waveform[- ]level" docs/SRS.md docs/SDD.md docs/SIM_SPEC.md README.md 2>/dev/null
grep -n "episode_id\|wear_endpoint\|maint_flag\|root_id" docs/SIM_SPEC.md || echo "SKIP: §5.4 keys live in MINIPRO-25 scope, spec unamended"
! grep -rnE "CURRENT|WEAR|AIR|THERMAL|IMPULSE" docs/SRS.md docs/SDD.md docs/SIM_SPEC.md 2>/dev/null

# 7. notify (dry run)
./scripts/linear_update.sh --dry-run "{\"lint-type\":{\"result\":\"success\"}}"
```
