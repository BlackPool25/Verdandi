# FINAL-f5-alt — dual-contract verdict: raise vs ok/side dict (READ-ONLY probe, no src/test edits)

Worktree: `m0b-t-build`. Scope: `tests/test_possibility.py:71-117` vs `src/possibility.py:382-413`.
No edits, no commits, no tests run, no Linear.

## Verdict: CONSISTENT

## 1. No test demands both a raise and a return

`tests/test_possibility.py` has 5 disjoint cases, each demanding exactly one leg:

- `71-78` `test_delay_starved_mass_holds_on_visible_delay`: `assert_delay_starved_mass(4, 6, 2)` → `out["ok"] is True` (return only, no raise). Compatible with impl `src/possibility.py:413` `visible` side (shield defaults 0, `6 < 4` false).
- `81-88` `test_delay_starved_mass_rejects_starvation_from_nothing`: `(2, 9, 2)` → `pytest.raises(AssertionError, match="CONSERVATION")` (raise only, no return asserted).
- `91-100` `test_delay_starved_mass_flags_buffer_decoupled_delay`: `(6, 1, 2, buffer_shield_steps=0.0)` → `pytest.raises(AssertionError, match="VISIBILITY")` (raise only).
- `103-108` `test_delay_starved_mass_shielded_delay_passes`: `(6, 1, 2, buffer_shield_steps=6.0)` → `out["ok"] is True and out["side"] == "shielded"` (return only).
- `111-117` `test_delay_starved_mass_vacuous_without_downstream`: `(6, 0, 0)` → `out["ok"] is True and out["side"] == "vacuous"` (return only).

Zero lines assert `raises` + `out[...]` in the same test. The contract is partitioned by input, not doubled on one input.

## 2. Implementation partitions inputs disjointly (src/possibility.py:382-413)

- `399-400`: `if n_downstream == 0: return {"ok": True, "side": "vacuous"}` — vacuous short-circuits before any raise; matches `111-117`.
- `401-405`: `if starved > injected * n_downstream: raise AssertionError("CONSERVATION...")` — matches `81-88` (`9 > 2*2`).
- `406-410`: `if starved < injected - buffer_shield_steps: raise AssertionError("VISIBILITY...")` — matches `91-100` (`1 < 6-0`).
- `411-412`: `if buffer_shield_steps > 0 and starved < injected: return shielded` — matches `103-108` (`1 < 6-6=0` false for the raise, then `6.0>0 and 1<6` true).
- `413`: fallthrough `return visible` — matches `71-78`.

Ordering note: an input violating both gates (e.g. tiny injected, huge starved with large shield) hits CONSERVATION first (`401` before `406`). That is deterministic priority, not contradiction — no test pins the double-violation order, so no conflict.

Side labels are mutually exclusive by construction: `vacuous` ⇔ `n==0`; `shielded` ⇔ pass + `shield>0 and starved<injected`; `visible` ⇔ pass + otherwise.

## 3. Precedent in src/ for raise-on-fail / value-on-pass

- `src/twin.py:2454-2549` `check_variant_gate(..., strict=False)`: returns `{"passed": False/True, ...}` dict by default, raises `ValueError` when `strict=True` — established dual contract; cf. `tests/test_twin_stratification_funnel.py:632-646` (report asserts) + `644-646` (`pytest.raises(ValueError)` in strict mode), and `649-679` same pattern for pileup.
- `src/evidence.py:118-125` `validate_evidence_floor` / `128-135` `validate_node_cap`: return value on pass, raise `ValueError` on violation (validate-or-raise idiom).
- `src/dataset_export.py:62-94` `assert_warmup_excluded`: `assert_*` name with raise-on-violation semantics (returns `None` on pass here; F5's dict return is a richer pass value, same shape of contract).
- No `raise AssertionError` precedent in `src/` (grep: zero hits outside `possibility.py`), but `tests/test_dataset_contract.py:470-491` and `test_dataset_v4_contract.py:713-734` already use `pytest.raises(AssertionError, match="Zero-join contract violation...")`, so AssertionError-as-contract is an accepted test idiom.

## Conclusion

CONSISTENT: raise on violation, dict on pass, with `vacuous/shielded/visible` disjoint. No case demands both. Precedent (`check_variant_gate` strict/report, `validate_*`, `assert_warmup_excluded`) supports the pattern.
