#!/usr/bin/env bash
# T12 quality gates — one invocation, fails fast with file:line evidence.
# Mirrors the CI mapping documented in docs/FRONTEND.md (Gates section).
set -euo pipefail
cd "$(dirname "$0")/.."

echo "== [1/5] palette-audit =="
npm run palette-audit

echo "== [2/5] scope-grep =="
node scripts/scope-grep.mjs

echo "== [3/5] tsc =="
npx tsc --noEmit

echo "== [4/5] vitest (unit specs) =="
npx vitest run

echo "== [5/5] src/ untouched =="
ROOT="$(git rev-parse --show-toplevel)"
STAT="$(git -C "$ROOT" diff --stat -- src/ | tr -d '[:space:]')"
test -z "$STAT" || { git -C "$ROOT" diff --stat -- src/; echo "GATE FAIL: src/ modified"; exit 1; }

echo "GATES GREEN"
