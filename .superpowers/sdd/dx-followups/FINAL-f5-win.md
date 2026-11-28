# FINAL F5 — Windows CI audit: `assert_delay_starved_mass` (pure arithmetic)

**Scope:** read-only audit of `src/possibility.py` (379 lines), `probe_delay.py` (42 lines), `tests/test_possibility.py` (117 lines) in worktree `m0b-t-build`.
**Verdict: 0 blockers.** Nothing about the module blocks Windows CI. The function to add is pure arithmetic.

## 1. `src/possibility.py` — clean
- Imports: `math` only (top-level line 13; function-local `import math` in `kbest_paths`, `upstream_paths` — redundant but harmless, stdlib, cross-platform). No `os`, `sys`, `pathlib`, `subprocess`, `open()`, `Path()`.
- No `fcntl`, `termios`, `resource`, `pty`, `os.fork`, `os.mkfifo`, `signal`, `multiprocessing`, `/tmp`, `/dev/` — grep clean.
- No hardcoded paths, no env vars, no shell-outs, no symlinks, no file I/O at all.
- All logic is dict/list/float arithmetic + BFS over in-memory edge dicts (`_reverse`, `_bfs`, `neighborhood`, `flow_teleport`, `best_cause_path`, `_all_paths`, `kbest_paths`, `upstream_paths`, `best_path`, `rank_nodes`). Deterministic; `sorted()` used for iteration order (lines 42, 74, 276, 347) — locale-independent for ASCII machine IDs.
- Python-version surface: `from __future__ import annotations`, `str | None` (line 102), frozenset/generics annotations — requires 3.10+. Same requirement on Linux and Windows; not Windows-hostile, just pin CI to 3.10+ (already the case per repo).
- Line 137 `path.insert(0, back[path[0]])  # type: ignore[arg-type]` — typing-only, no runtime effect.

## 2. `tests/test_possibility.py` — clean
- Imports: `pandas`, `numpy` (inside fixture), `pytest` (inside tests) — all cross-platform wheels.
- No `fcntl`/`fork`/`signal`/`multiprocessing`/`resource` — one grep hit is a false positive (comment line 96: "empty buffers").
- No hardcoded absolute paths, no `/tmp`, no `os.*`, no subprocess, no socket, no timing-sensitive asserts. All asserts are exact set/dict comparisons or float tolerances (`1e-9`, `0.2`).
- Note (not a Windows issue): tests import `assert_delay_starved_mass` from `src.possibility`, which does **not yet exist** in the read module — that is the F5 function to add. Its tested contract (ints/floats in, dict with `ok`/`side` out, `AssertionError("CONSERVATION"|"VISIBILITY")` on failure) is pure arithmetic with no platform surface, so adding it introduces zero Windows risk provided it keeps the module's current import profile (stdlib `math` only, no I/O).

## 3. `probe_delay.py` — not part of CI surface, non-blocking
- Ad-hoc analysis script (not imported by `src/` or `tests/`). Uses relative forward-slash paths (`docs/m0b_mass_full_manifest.json`, `artifacts/m0b_mass_c*.parquet`) + `glob` + `pandas.read_parquet`. Forward slashes are accepted by CPython on Windows; `glob` is cross-platform. Would only matter if CI executed this script directly, which it should not (it also assumes CWD = repo root and pre-existing artifacts). No `fcntl`/`fork`/`signal`/`multiprocessing`. **Not a blocker.**

## 4. Checklist
- [x] No `fcntl` / `termios` / `resource` / `pty`
- [x] No `os.fork` / `multiprocessing` (nothing to guard with `if __name__ == "__main__"`)
- [x] No `signal` handling
- [x] No hardcoded `/` absolute paths, no `/tmp`, no `/dev/`
- [x] No `os`/`sys`/`pathlib`/`subprocess`/`open()` in `src/possibility.py`
- [x] Test deps (`pandas`, `numpy`, `pytest`) have Windows wheels
- [x] Target function contract is pure arithmetic (numbers in, dict out / raise) — confirm implementation adds no imports beyond `math`

**Blocker count: 0.**
