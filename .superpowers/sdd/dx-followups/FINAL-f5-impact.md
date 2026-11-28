# FINAL F5 impact — src.possibility importer check (read-only)

Worktree: `C:\Users\athma\OneDrive\Desktop\my projects\Verdandi\.worktrees\m0b-t-build`
Scope: `src/`, `scripts/`, `tests/`, `services/`, `frontend/` (source `.py`/`.ts`/`.tsx`/`.js` only; `__pycache__` and `frontend/node_modules` excluded as build/vendor noise).
Method: `Select-String -Pattern 'possibility'` + `Select-String -Pattern 'assert_delay_starved_mass'` over source files, plus full read of `src/possibility.py` (413 lines) and `tests/test_possibility.py` (117 lines). No edits, no commits, no tests, no Linear.

## (1) Full importer list (file:line)

32 import lines across 9 files. `services/` = 0. `frontend/` app source = 0 (only English-word "possibility" hits inside `frontend/node_modules` vendor text — not code imports).

### src/ (2 lines, 2 files)
- `src/diagnose.py:343` — `from src.possibility import neighborhood, rank_nodes, upstream_paths` (function-local lazy import)
- `src/report.py:23` — `from src.possibility import best_path` (function-local lazy import)
- `src/calibration_artifact.py:9` — comment/docstring mention only ("rank_nodes possibility probs"), NOT an import.

### scripts/ (5 lines, 3 files)
- `scripts/eval_paths.py:46` — `from src.possibility import kbest_paths` (function-local)
- `scripts/eval_paths.py:99` — `from src.possibility import neighborhood` (function-local)
- `scripts/eval_paths.py:120` — `from src.possibility import flow_teleport` (function-local)
- `scripts/eval_jev.py:59` — `__import__("src.possibility", fromlist=["upstream_paths"]).upstream_paths(...)` (dynamic, function-local)
- `scripts/probe_family_prune.py:46` — `from src.possibility import neighborhood` (function-local)
- `scripts/fit_calibration.py:85` — string literal "possibility probs", NOT an import.

### tests/ (25 lines, 4 files)
- `tests/test_cascade_path.py:3` — `from src.possibility import best_path` (module top-level)
- `tests/test_cascade_path.py:7,21,35` — `from src.possibility import best_cause_path` (3x, function-local, one per test)
- `tests/test_possibility.py:18` — `from src.possibility import neighborhood`
- `tests/test_possibility.py:31,45,59` — `from src.possibility import rank_nodes` (3x)
- `tests/test_possibility.py:72,84,94,104,112` — `from src.possibility import assert_delay_starved_mass` (5x, one per F5 delay test; calls at :77, :88, :100, :107, :116)
- `tests/test_rerank_teleport.py:44` — `from src.possibility import flow_teleport`
- `tests/test_routes.py:11` — `from src.possibility import kbest_paths`
- `tests/test_routes.py:29,44,56,77,121,129,138,144,158,165` — `from src.possibility import upstream_paths` (10x, function-local per test)

### services/ — 0 importers
Files present (`services/sim_bridge/app.py`, `models.py`, `schema.py`, `sse.py`, tests, etc.); `Select-String 'possibility'` returns no hits.

### frontend/ app source — 0 importers
No hits under `frontend/src|app|lib`. Only `frontend/node_modules/**` English-prose hits (babel/chai/dagre licenses etc.), unrelated.

### Rank_nodes / neighborhood / module-import subset
For the parenthetical scope: 7 lines across 4 files — `src/diagnose.py:343` (both names), `scripts/eval_paths.py:99`, `scripts/probe_family_prune.py:46`, `tests/test_possibility.py:18,31,45,59`. No bare `import src.possibility` module-style imports found; no `from src.possibility import *` anywhere (verified, zero hits).

## (2) Adding one new pure function breaks none

- All 32 import sites are **explicit named `from`-imports** (or one explicit `__import__` with `fromlist=["upstream_paths"]`). No star-imports, so a new top-level `def` cannot shadow or alter any existing binding.
- `src/possibility.py` defines **no `__all__`** (verified via `^def|^class|^__all__` grep: 11 defs, zero `__all__`), so no export list to update or break.
- `src/possibility.py` has **zero internal imports** (only stdlib `import math` at :13 plus two function-local `import math` at :176/:234). A new pure function adds no import edge, hence no circular-import risk for `diagnose.py` / `report.py` / scripts.
- All non-test importers use **function-local lazy imports**, so module load order is unaffected; tests use top-level/function-local explicit names that remain bound to the same objects.
- A pure function (no mutation of existing functions, no signature changes, no global state) cannot change `neighborhood` / `rank_nodes` / `best_path` / `upstream_paths` / `kbest_paths` / `best_cause_path` / `flow_teleport` behavior. The 5 `assert_delay_starved_mass` test imports are the intended consumers, not breakage vectors.
- Verdict: **adding one new pure function breaks 0 of 32 import lines.**

## (3) Name collision on `assert_delay_starved_mass`: NO

- Exactly **one definition** in the code tree: `src/possibility.py:382` — `def assert_delay_starved_mass(` (the F5 implementation itself; currently uncommitted per `git status --short`: `M src/possibility.py`, `M tests/test_possibility.py`).
- Zero other `def` / assignment occurrences in `src/`, `scripts/`, `tests/`, `services/`, `frontend/` source. The remaining 11 hits are the 5 test import lines + 5 test call sites in `tests/test_possibility.py` (:72/:77, :84/:88, :94/:100, :104/:107, :112/:116) plus one speculative signature sketch in `.superpowers/sdd/dx-followups/FINAL-probeassist.md:86` (markdown, not code).
- `git log --oneline -5 -- src/possibility.py` shows last committed touch `5823dc7`; the working-tree `def` at :382 is the new F5 addition. No competing implementation exists to collide with.

## Return values

- Importer count: **32 import lines across 9 files** (src 2 / scripts 5 / tests 25; services 0; frontend 0). Rank_nodes/neighborhood subset: 7 lines across 4 files.
- Collision on `assert_delay_starved_mass`: **NO**.
