# FINAL-f5-perf — perf check: `assert_delay_starved_mass` is O(1), zero hot-path callers

Worktree: `m0b-t-build`. Read-only: no edits, no commits, no tests, no Linear. Only new file is this report.

Gate under check: `src/possibility.py:382` `assert_delay_starved_mass(injected, starved, n_downstream, buffer_shield_steps=0.0)` (lines 382–413).

## 1. Caller count: 0 production callers

Grep results (`assert_delay_starved_mass`):

- `src/` → 1 match: the `def` at `src/possibility.py:382`. Zero call sites in `src/`.
- `scripts/` → 0 matches.
- `services/` → 0 matches.
- `tests/test_possibility.py` → 10 textual matches = 5 test functions only (5 `from src.possibility import assert_delay_starved_mass` + 5 calls at lines 77, 88, 100, 107, 116). No other test file references it.
- Remaining matches repo-wide are report/docs prose (`progress.md:25`, `FINAL-probeassist.md`, `FINAL-oraclefinal.md`, `FINAL-f5-linear.md`, `FINAL-dqcomplete.md`) — not code.

Per-window / per-episode hot paths verified clean:

- `src/diagnose.py:343` (per-window gated diagnosis) imports only `neighborhood, rank_nodes, upstream_paths` — does not import or call the gate. `rank_nodes`/`upstream_paths` bodies contain no gate call (whole-`src/` grep above proves it).
- `src/report.py:23` imports only `best_path` — no gate.
- `src/twin.py` per-episode gates (`check_variant_gate`, `check_funnel_gate`) contain no reference (covered by zero `src/` call-site result).
- So no per-window, per-episode, or per-fault loop invokes the gate today. Wiring it in later would add one call per episode at most, not per tick/window.

## 2. Import verdict: trivial — zero new imports, pure arithmetic

`src/possibility.py:11-13` header is `from __future__ import annotations` + `import math` only — unchanged by the gate (the gate hunk at 382–413 adds no import line). Gate body uses only:

- float comparisons (`starved > injected * n_downstream`, `starved < injected - buffer_shield_steps`, `buffer_shield_steps > 0 and starved < injected`),
- f-string `AssertionError` raises,
- 3 small dict-literal returns (`{"ok": True, "side": ...}`).

No `numpy`/`pandas`/`torch`, no file/artifact I/O, no loops, no recursion, no allocation beyond one tiny dict. Complexity O(1) time, O(1) memory; module import cost unchanged (stdlib `math` only, already imported).

## Return

- **Caller count: 0** production callers (1 `def` + 5 test-only calls, no `src/`/`scripts/`/`services/` call sites; no per-window/per-episode invocation).
- **Import verdict: trivial** — no new imports; pure-arithmetic O(1) gate, `possibility.py` import cost unchanged.
