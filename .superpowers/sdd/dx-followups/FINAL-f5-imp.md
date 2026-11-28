# FINAL F5 implementation report — `assert_delay_starved_mass` (TDD GREEN)

## Function appended to `src/possibility.py`

```python
def assert_delay_starved_mass(
    injected: float,
    starved: float,
    n_downstream: int,
    buffer_shield_steps: float = 0.0,
) -> dict:
    """Delay/starvation mass balance (Twin F5 conservation + visibility).

    Conservation: downstream starvation cannot exceed what the injected
    delay can explain across downstream machines
    (starved <= injected x n_downstream), else the starvation came
    from nothing. Visibility: starvation cannot hide below what
    buffers can absorb (starved >= injected - buffer_shield_steps),
    else the delay went somewhere path tuning must not trust
    (caps/backpressure/failover). Sink origins with no downstream
    are vacuous.
    """
    if n_downstream == 0:
        return {"ok": True, "side": "vacuous"}
    if starved > injected * n_downstream:
        raise AssertionError(
            f"CONSERVATION: starved={starved} exceeds "
            f"injected={injected} x n_downstream={n_downstream}"
        )
    if starved < injected - buffer_shield_steps:
        raise AssertionError(
            f"VISIBILITY: starved={starved} below "
            f"injected={injected} - buffer_shield_steps={buffer_shield_steps}"
        )
    if buffer_shield_steps > 0 and starved < injected:
        return {"ok": True, "side": "shielded"}
    return {"ok": True, "side": "visible"}
```

Notes: matches file style (`from __future__ import annotations` already present,
typed signature, no new imports). Side logic: `vacuous` when `n_downstream == 0`;
`shielded` only when a positive shield was needed (`shield > 0` and
`starved < injected`, which for passing cases is equivalent to the shield
absorbing the `injected - starved` gap); otherwise `visible`.

## Test output

Command (worktree `C:\Users\athma\OneDrive\Desktop\my projects\Verdandi\.worktrees\m0b-t-build`):

```
python -m pytest tests/test_possibility.py -q -p no:cacheprovider
```

Result:

```
.........                                                                [100%]
9 passed in 0.84s
```

Also verified with
`PYTHONPATH=C:\Users\athma\AppData\Local\Temp\opencode\pycompat;<worktree>`:
9 passed.

## Scope compliance

- Edited ONLY `src/possibility.py` (appended function, nothing else changed).
- Did NOT touch `tests/`, `probe_delay.py`, Linear, or any other file.
- Did NOT commit.
