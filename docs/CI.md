# CI — brutal gates for Verdandi

Pipeline: `.github/workflows/ci.yml`. Triggers: push/PR to `main`, weekly cron (pip-audit), manual dispatch. Runner `ubuntu-22.04` pinned, Python 3.14, `uv`-ready pip cache. Wall budget <15min.

| Job | Gates → fail if |
|---|---|
| `lint-type` | ruff check/format, mypy errors, or `src/` imports `spike/` (quarantine) |
| `battery` | any pytest k1–k5/battery marker red; `scripts/check_gates.py` rejects battery.csv (F1<0.85, AC@1<0.70 intra/cross, flip≥0.40/partition, p99>3, wall≥600s, grounding<0.95); coverage <80% |
| `killbars-security` | replay `--seed 7` ×2 diverges; bandit HIGH; pip-audit fixable CVE |
| `e2e-demo` | `demo/run.sh` exits non-zero or exceeds budget |
| `adversarial` | hostile/malformed pass-through; mutation-inversion vacuous (ΔF1 ≤0.1) |
| `docs-links` | stale tokens (`VETO_M5`, `6/6 machines`, `TODO(owner)`) in normative docs/src; broken markdown links (lychee) |
| `notify` | always runs: uploads artifacts (JSONL, battery.csv, junit — 30d) + posts Linear status via `LINEAR_API_KEY` secret |

Branch protection on `main`: PR + 1 review, all jobs required, dismiss stale reviews, no direct push. Weekly cron opens auto-issue on CVE. Secrets: `LINEAR_API_KEY` in repo secrets; never in files.
