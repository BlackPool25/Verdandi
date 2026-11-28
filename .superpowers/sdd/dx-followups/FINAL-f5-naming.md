# FINAL-f5-naming — `assert_delay_starved_mass` naming verdict: needs-rename

Worktree: `m0b-t-build`. Read-only review. No edits to `src/`, no tests, no commits, no Linear.

## Verdict: needs-rename

Proposed `assert_delay_starved_mass(injected, starved, n_downstream, buffer_shield_steps=0.0)`
raising `AssertionError("CONSERVATION..."/"VISIBILITY...")` on failure and returning
`{"ok": True, "side": "vacuous"|"shielded"|"visible"}` on success is **inconsistent**
with codebase conventions on three axes: (1) `assert_` prefix contract, (2) exception type,
(3) module-local `src/possibility.py` style + eval-script gate consumption.

Suggested rename direction (for F5 owner, not applied): `check_delay_starved_mass`
or `verify_delay_starved_mass`, raising `ValueError` (repo standard) or returning a
result/status dict without raising. `assert_` in this repo means void validator.

## Evidence

### 1. `def assert_*` in `src/` = exactly 2, both `-> None`, both `raise ValueError`, never return a dict

Grep `src/` for `def assert_` → 2 hits only:

- `src/dataset_export.py:62`: `def assert_warmup_excluded(df: Any) -> None:` — raises
  `ValueError` on warmup rows (`:86`, `:93`), returns `None` implicitly. Docstring:
  "raises ValueError".
- `src/train_pipeline.py:179`: `def assert_no_scaler_artifact(directory: str | pathlib.Path) -> None:`
  — raises `ValueError(f"LEAKAGE VIOLATION...")` (`:183-185`), returns `None`.
  Test enforces it: `tests/test_train_pipeline.py:148` asserts
  `tp.assert_no_scaler_artifact(tmp_path) is None`.

No other `def assert_*` exists in `src/`. A function that returns
`{"ok","side"}` breaks this contract; a void `assert_` that also serves as a
status query (ok/side) has no precedent.

### 2. `raise AssertionError` with keywords = zero precedent in `src/` outside the proposal

- Grep `src/` for `AssertionError` → only 2 hits, both in the proposed
  `src/possibility.py:402,407` (`raise AssertionError(f"CONSERVATION...")`,
  `raise AssertionError(f"VISIBILITY...")`).
- Grep `src/` for `raise ValueError` → 100+ hits across `calibrate.py`, `config.py`,
  `dataset_export.py`, `detect.py`, `evidence.py`, `gates.py:70`, `train_pipeline.py`,
  `twin.py`, etc. Contract violations (leakage, schema, warmup, rate budget,
  variant/funnel gates) uniformly raise `ValueError`, never `AssertionError`.
- `tests/test_possibility.py:87,99` (`pytest.raises(AssertionError, match="CONSERVATION"/"VISIBILITY")`)
  therefore encodes a new exception-type + keyword-message pattern no `src/` caller
  or eval script handles.

### 3. `src/possibility.py` module style: never raise, return normalized shapes

Per `.superpowers/sdd/dx-followups/FINAL-f5-style.md` (read-only review of 379-line
`possibility.py` pre-F5): "No `raise` / `assert` / `try/except` anywhere in the file."
Conventions are fallback returns (`or 1.0`, `1e-12` floor, `sorted(...)`), with returns:

- `dict[str,float]` normalized to sum 1 (`flow_teleport`, `rank_nodes`),
- `tuple[list[str],float]` / `list[tuple[list[str],float]]` (`best_path`, `kbest_paths`, `upstream_paths`),
- `tuple[list[str],float,dict[str,float]]` (`best_cause_path`).

Proposed `-> dict` returning `{"ok": True, "side": ...}` matches none of these;
`rank_nodes` optional second shape is `dict | tuple[dict, list[str]]`, not an ok/side envelope.
Public names are scoring/verb phrases (`neighborhood`, `flow_teleport`, `best_cause_path`,
`kbest_paths`, `upstream_paths`, `best_path`, `rank_nodes`) — no `assert_` prefix.

### 4. How eval scripts consume similar gates: pure `bool`/tuple, `check_/require_/validate_` names

- `scripts/run_m0b_baseline.py:114-119`: `gates.delay_gate(...) or gates.loss_gate(...) or
  gates.loss_combo_gate(...) or gates.breakdown_gate(...)` — all `-> bool` (`src/gates.py:23,33,38,62`).
- `scripts/run_m0b_baseline.py:46-50`, `scripts/m0b_vus_appendix.py:60-63`,
  `scripts/measure_cusum_p0.py:40-65`: `gates.bernoulli_cusum_weights` /
  `gates.kit_outcomes_from_events` / `gates.bernoulli_cusum_update` — pure
  tuple/list returns; the one failure mode raises `ValueError` (`gates.py:70`), not `AssertionError`.
- `scripts/check_gates.py`, `scripts/check_anomaly_quality.py:180` treat gates as boolean
  predicates to evaluate, not try/except `AssertionError` tripwires.
- Raising validators that filter/return use `require_`/`check_`/`validate_` prefixes:
  `src/train_pipeline.py:188 require_post_warmup(df) -> pd.DataFrame` (delegates to
  `assert_warmup_excluded`), `src/config.py:364 check_config`,
  `src/twin.py:2454 check_variant_gate, :2552 check_funnel_gate, :2900 check_wall_tripwire`,
  `src/evidence.py:118 validate_evidence_floor`. A raise-plus-status gate belongs under
  `check_`/`verify_`, not `assert_`.

## Conclusion

Keep test intent (conservation `starved <= injected*n`, visibility
`starved >= injected - shield`, vacuous `n==0`, shielded side) but rename out of
`assert_` and align on `ValueError` or a non-raising status return. Verdict word: **needs-rename**.
