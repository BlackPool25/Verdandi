# FINAL F5 Baseline — test_possibility.py (pre-change before-picture)

Date: 2026-11-25
Worktree: `C:\Users\athma\OneDrive\Desktop\my projects\Verdandi\.worktrees\m0b-t-build`
Scope: `tests/test_possibility.py` — green-only selection (another lane implements; compare after).

## Command (green-only)
```powershell
$env:PYTHONPATH='C:\Users\athma\AppData\Local\Temp\opencode\pycompat;C:\Users\athma\OneDrive\Desktop\my projects\Verdandi\.worktrees\m0b-t-build'
python -m pytest tests/test_possibility.py -q -p no:cacheprovider -k "neighborhood or ranking or fork or unreachable"
```

## Result (exact)
```
4 passed, 5 deselected in 1.45s (repeat run: 4 passed, 5 deselected in 1.28s)
```

Verbose (`-v`) green list — all PASSED:
- `tests/test_possibility.py::test_neighborhood_restricts_to_one_hop_plus_changed`
- `tests/test_possibility.py::test_ranking_prefers_earliest_causal_origin`
- `tests/test_possibility.py::test_fork_shares_mass_both_branches_ranked`
- `tests/test_possibility.py::test_unreachable_change_flagged_independent`

## Counts
- GREEN (selected, passing): 4
- DESELECTED (not run in this baseline command): 5
- RED (expected, NOT executed here — listed by name only via `--collect-only` + file read): 5

## Expected RED — 5 `delay_starved_mass` tests (names only, not run)
1. `test_delay_starved_mass_holds_on_visible_delay`
2. `test_delay_starved_mass_rejects_starvation_from_nothing`
3. `test_delay_starved_mass_flags_buffer_decoupled_delay`
4. `test_delay_starved_mass_shielded_delay_passes`
5. `test_delay_starved_mass_vacuous_without_downstream`

Full collect: 9 tests total (4 green + 5 red). No red test was executed for this baseline.

## Notes
- Read-only baseline; no source files edited, no commit, no Linear touch.
- pytest config: `pytest.ini` present; `-p no:cacheprovider` used per instruction.
- Python 3.11.0, pytest 8.4.2 (from session header).
