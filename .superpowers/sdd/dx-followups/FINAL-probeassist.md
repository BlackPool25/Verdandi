# FINAL-probeassist — delay STARVED-mass probe assist (READ-ONLY, F5 owns implementation)

Source worktree: `m0b-t-build`. F5 lane still active and owns
`src/possibility.py`, `tests/test_possibility.py`, `probe_delay.py`.
This report makes ZERO edits to those files, runs NO pytest, touches NO Linear, commits NOTHING.
Probe `probe_delay.py` was executed once (verified side-effect-free by static read:
only `json.load` + `glob` + `pd.read_parquet` column-filtered + `print`; no writes)
with a 240 s timeout. It completed in seconds.

## 1. Empirical question the probe answers

> For a `delay` fault injected at C2 (line C: C2→C6→C7 via buffers C26/C67),
> does the withheld production mass reappear as downstream STARVED mass at
> C6/C7, or is it absorbed/deflected elsewhere (buffers, caps, backpressure, failover)?

Method (from full static read of `probe_delay.py`, 42 lines):
- Manifest `docs/m0b_mass_full_manifest.json`: first 6 rows with
  `class == 'delay'` and `origin == 'C2'`; each gives `(t0, dur)`.
- Trace `artifacts/m0b_mass_c*.parquet` (column-filtered to
  `episode_id, step, state_C2/C6/C7, tput_C2/C6/C7, buffer_C26/C67`):
  early-break once all 6 episodes located.
- Baseline rates from 60 pre-onset steps: `rate = tput.sum()/60`.
- Window `L = dur + H`, `H = 30`: `with_O = rate_O*L − Σtput_C2`,
  `miss_6/7 = rate_6/7*L − Σtput_C6/7`, `S = #(state_C6==STARVED) + #(state_C7==STARVED)`
  over `[t0, t0+dur+H)`, `bufq = buffer_C26 + buffer_C67` at `t0−1`.

Live output (6/6 episodes found):

| ep | with_O | miss6 | miss7 | sum_miss | S_starved | bufq |
|----|--------|-------|-------|----------|-----------|------|
| 41218 | 0.83 | 0.83 | 0.83 | 1.67 | 7 | 2.0 |
| 41220 | 0.50 | 0.50 | 0.50 | 1.00 | 7 | 0.0 |
| 41221 | 1.00 | 1.00 | 0.00 | 1.00 | 9 | 0.0 |
| 41242 | 0.50 | 0.50 | −0.50 | 0.00 | 3 | 0.0 |
| 41281 | 0.83 | 0.83 | −0.17 | 0.67 | 3 | 0.0 |
| 41291 | 1.00 | 1.00 | 1.00 | 2.00 | 9 | 0.0 |

Reading: baseline rate is 0.167 everywhere (≈1 unit / 6 steps).
With `bufq ≈ 0` (5/6 episodes exactly 0.0, one 2.0), every C2 delay IS
visible downstream as 3–9 STARVED steps across C6+C7 — the "visible delay"
regime exists empirically, so a conservation+visibility gate is well-founded.
But (a) STARVED-step counts (3–9) overstate throughput-miss units (0–2),
so the gate must compare *steps to steps* with fan-out multiplier, not units
to steps; (b) ep 41242 (`with_O=0.50` yet `sum_miss=0.00`, `S=3`) is a live
decoupling specimen — withheld mass that never shows as downstream miss —
which is exactly what the VISIBILITY leg must catch; (c) no stocked-buffer
episode appears in this slice (`bufq≤2`), so the shielded-absorption leg
(`buffer_shield_steps`) cannot be calibrated from these 6 alone and must stay
a parameter, not a fitted constant.

## 2. Which failing assertions the probe output unblocks

`src/possibility.py` (379 lines, fully read) defines `neighborhood`,
`flow_teleport`, `best_cause_path`, `kbest_paths`, `upstream_paths`,
`best_path`, `rank_nodes` — but NO `assert_delay_starved_mass`.
All 5 delay tests in `tests/test_possibility.py` (lines 71–117) therefore fail
at collection/import with `ImportError` (failing for the right RED reason;
pytest deliberately NOT rerun per constraints). Probe output unblocks each one:

- `test_delay_starved_mass_holds_on_visible_delay` — `(4, 6, 2) → ok`:
  probe eps 41218/41291 (`S=7–9`, `bufq≈0–2`) are the empirical analogue —
  modest injected busy-steps fan out to `S ≤ injected × n_downstream`
  with empty buffers, so the conservation leg `S ≤ injected*n` holds.
- `test_delay_starved_mass_rejects_starvation_from_nothing` — `(2, 9, 2)`
  must raise `CONSERVATION`: probe bounds the other side — no episode shows
  `S=9` from ~2 injected steps without a multiplier violation; conservation
  with fan-out factor `n_downstream` is the correct upper fence.
- `test_delay_starved_mass_flags_buffer_decoupled_delay` — `(6, 1, 2,
  shield=0.0)` must raise `VISIBILITY`: ep 41242 is the specimen
  (`with_O>0` but `sum_miss=0.00`, tiny `S=3`) — delay mass that vanishes
  with empty buffers means caps/backpressure/failover, so path tuning must
  distrust the episode. Probe justifies failing loud here.
- `test_delay_starved_mass_shielded_delay_passes` — `(6, 1, 2, shield=6.0)
  → ok/shielded`: probe has NO stocked-buffer case (max `bufq=2.0`), proving
  the shield term must remain an explicit input (`buffer_shield_steps`,
  e.g. pre-onset `buffer_C26+buffer_C67` or equivalent dwell cover), not
  something inferable from STARVED counts alone.
- `test_delay_starved_mass_vacuous_without_downstream` — `(6, 0, 0) →
  ok/vacuous`: topology confirm (`twin.py`: `C2→C6→C7`; sink tails/PKG/ASM2
  have no line-internal downstream) — with `n_downstream==0` there is nothing
  to conserve against; probe trivially agrees (nothing to count).

## 3. Smallest implementation sketch for the F5 owner (signatures + logic, no edits made)

```python
def assert_delay_starved_mass(
    injected_steps: float,
    starved_steps: float,
    n_downstream: int,
    buffer_shield_steps: float = 0.0,
    *,
    tol: float = 1e-9,
) -> dict:
    """Conservation + visibility gate for delay→STARVED mass.

    Conservation (no starvation from nothing):
        starved <= injected * n_downstream + tol
        else raise AssertionError("CONSERVATION ...").
    Visibility (no silent / decoupled delay):
        if n_downstream == 0: return {"ok": True, "side": "vacuous", ...}
        deficit = injected - buffer_shield_steps - starved
        if deficit > tol:
            if buffer_shield_steps >= injected - starved - tol:
                absorbed -> return {"ok": True, "side": "shielded", ...}
            raise AssertionError("VISIBILITY ...")
        return {"ok": True, "side": "visible", ...}
    """
    if n_downstream == 0:
        return {"ok": True, "side": "vacuous",
                "injected": injected_steps, "starved": starved_steps}
    if starved_steps - injected_steps * n_downstream > tol:
        raise AssertionError(
            f"CONSERVATION: starved={starved_steps} > "
            f"injected={injected_steps} * n={n_downstream}")
    if starved_steps + buffer_shield_steps + tol < injected_steps:
        raise AssertionError(
            f"VISIBILITY: starved={starved_steps} + shield={buffer_shield_steps} < "
            f"injected={injected_steps} (delay went to caps/backpressure/failover)")
    side = "shielded" if (
        buffer_shield_steps > tol and starved_steps < injected_steps) else "visible"
    return {"ok": True, "side": side,
            "injected": injected_steps, "starved": starved_steps,
            "n": n_downstream, "shield": buffer_shield_steps}
```

Calibration notes from probe (for F5 to apply, not asserted here):
- Count `starved_steps` as STARVED *steps* summed over downstream machines
  (`S` in probe), `injected_steps` as injected busy/delay *steps* (dur-like),
  `n_downstream` = number of line-internal downstream machines with STARVED
  exposure (2 for C2→C6/C7). Do NOT compare throughput-miss units to S
  directly — probe shows units (0–2) ≪ steps (3–9).
- `buffer_shield_steps` = pre-onset queued cover (`buffer_C26+buffer_C67` at
  `t0−1`, i.e. probe `bufq`, possibly scaled by rate); default 0.0 keeps the
  decoupled-delay tripwire armed (ep 41242 pattern).
- `H=30` post-window in the probe inflates S with recovery starvation; if F5
  wires this gate to episode features, keep the window bounded or pass
  `tol`/slack explicitly rather than baking H into the assertion.
- Vacuous leg keyed strictly on `n_downstream == 0` (sink origins:
  tails, PKG, ASM2) per the test contract.

Constraints honored: no writes to `src/possibility.py`,
`tests/test_possibility.py`, or `probe_delay.py`; no commits; no pytest run;
no Linear access. Only new file is this report.
