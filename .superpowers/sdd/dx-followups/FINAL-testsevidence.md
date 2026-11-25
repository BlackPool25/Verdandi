# FINAL Test Evidence — m0b-t-build worktree

Date (UTC): 2026-11-25
Worktree: `C:\Users\athma\OneDrive\Desktop\my projects\Verdandi\.worktrees\m0b-t-build`
Note: `tests/test_possibility.py` EXPLICITLY EXCLUDED (F5 lane mid-TDD-RED, failures expected). Not run, not touched.

## (1) Python focused battery

Command (PowerShell, from worktree root):
```powershell
$env:PYTHONPATH='C:\Users\athma\AppData\Local\Temp\opencode\pycompat;C:\Users\athma\OneDrive\Desktop\my projects\Verdandi\.worktrees\m0b-t-build'
python -m pytest tests/test_calibration_gate.py tests/test_gate_obs_only.py tests/test_stacked_splits.py tests/test_eval_family_norm.py tests/test_eval_tev.py tests/test_eval_faithfulness.py tests/test_report_incident.py tests/test_phrase.py tests/test_rerank_teleport.py tests/test_ranker_calibration.py tests/test_battery_v2.py -q -p no:cacheprovider
```
Exit code: 0
Result: **85 passed, 1 skipped**, 1 warning (expected `calibrator artifact unreadable ... gate open` UserWarning in `test_calibrator_artifact_roundtrip`, from `src/calibration_artifact.py:42`)
Failures: none — no failure names to record.

## (2) Frontend vitest

Command (from `frontend/`):
```
npx vitest run
```
Exit code: 0
Result: **23 test files passed, 190 tests passed**, 0 failed. Duration ~2.23s.
Failures: none.

## (3) Frontend typecheck

Command (from `frontend/`):
```
npx tsc --noEmit
```
Exit code: 0
Result: clean, no output, no errors.
Failures: none.
