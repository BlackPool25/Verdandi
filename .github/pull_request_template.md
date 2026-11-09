## What
<!-- one line: feat/fix + scope -->

## Why
<!-- link issue / milestone M0-M5 -->

## Verification
- [ ] `ruff check src/ tests/ && ruff format --check src/ tests/` + `mypy src/`
- [ ] pytest markers run: <!-- e.g. -m "k1 or battery" -->
- [ ] `scripts/check_gates.py` bars unchanged (or L1 reclassification noted)
- [ ] CI green on this PR

## Risk
<!-- gate bars touched? config/compose touched? migration needed? -->
