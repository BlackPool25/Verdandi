# Agent rules — Verdandi (ForgeTrace)

## Stack (do not change unilaterally)
- One-command run: `./run.sh` (sim bridge + frontend). Tests: `python -m pytest tests/ -m "k1 or k2 or k3 or k4 or k5 or battery" -n auto -q`.
- Gates: `python scripts/check_gates.py --csv artifacts/battery.csv` (bars in README). Lint: `ruff check src/ tests/ && ruff format --check src/ tests/` + `mypy src/`.
- Never soften a gate bar without an L1 reclassification. Never import from `spike/` into `src/` (CI greps for it).

## Workflow
- One task = one branch `feat/<slug>` or `fix/<slug>`. Never push to `main`.
- Rebase before pushing: `git pull --rebase --autostash`. Conflicts: keep both sides' logic, never delete another author's test; ask if semantic.
- Commits: `feat(scope):` / `fix(scope):` / `docs:` / `chore:` / `test:` prefix, one logical change per commit.
- PRs need green CI (`lint-type`, `battery`, `killbars-security`) + 1 human review. Squash-merge.

## Authority (hard limits)
- Agents may: create branches, push branches, open PRs, run all checks.
- Agents may NOT: merge PRs, push to `main`, change gate bars, edit `.github/workflows/`, `compose*.yaml`, `src/config.py` without a human-approved plan.
- `main` merges are human-only.

## Done = all of
1. `ruff check`, `ruff format --check`, `mypy src/` clean.
2. Task's pytest markers green locally (or CI green).
3. `check_gates.py` bars unchanged or explicitly reclassified.
4. PR describes what changed + the verification run.
