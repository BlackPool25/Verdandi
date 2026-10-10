"""PRISSUE-23 (M0.2c wear-knee WSTATE): load-factored wear + MAINT_EVENT reset.

Covers:
1. Knee at ~192 loaded RUN steps for L=1.0 machines (0.8/(1/240)).
2. Post-knee rate exactly 5x pre-knee (1+BETA, BETA=4.0).
3. Load factoring per K_BY_GROUP (A/B=1.0, C=0.7, ASM/PKG/INSP=0.5, RWK=0.3).
4. MAINT_EVENT reset: endpoint drops vs no-reset; endpoint equals wear
   accumulated after the last reset; MAINT_EVENT rows in record events.
5. Determinism: same seed+maintenance twice -> identical digest/wstate/events.
6. Invalid maintenance raises ValueError.
7. Parquet wstate_<M> columns present for all 26 machines.
8. maint_flag False/unvalidated-True when empty vs True/validated on use.
"""

import numpy as np
import pytest

from src import config, dataset_export, twin

pytestmark = pytest.mark.k2

_T = config.T
_N = config.N_MACHINES
_ALPHA = config.WEAR["ALPHA"]
_KNEE = config.WEAR["KNEE"]
_BETA = config.WEAR["BETA"]


def _states_one_hot(run_steps, run_machine_idx=0):
    states = [["STARVED"] * _T for _ in range(_N)]
    states[run_machine_idx] = ["RUN"] * run_steps + ["STARVED"] * (_T - run_steps)
    return states


def test_wstate_knee_at_192_loaded_run_steps_l10():
    run_idx = config.MACHINE_INDEX["A0"]
    w = twin.compute_wear(_states_one_hot(192, run_idx))[run_idx]
    np.testing.assert_allclose(w, 0.8)
    w_over = twin.compute_wear(_states_one_hot(193, run_idx))[run_idx]
    assert w_over > 0.8


def test_wstate_post_knee_rate_exactly_5x_pre_knee():
    run_idx = config.MACHINE_INDEX["B2"]
    w192 = twin.compute_wear(_states_one_hot(192, run_idx))[run_idx]
    w193 = twin.compute_wear(_states_one_hot(193, run_idx))[run_idx]
    w194 = twin.compute_wear(_states_one_hot(194, run_idx))[run_idx]
    np.testing.assert_allclose(w193 - w192, _ALPHA)
    np.testing.assert_allclose(w194 - w193, 5.0 * _ALPHA)


def test_wstate_load_factored_by_group():
    run_steps = 192
    w_a = twin.compute_wear(_states_one_hot(run_steps, config.MACHINE_INDEX["A0"]))[
        config.MACHINE_INDEX["A0"]
    ]
    w_c = twin.compute_wear(_states_one_hot(run_steps, config.MACHINE_INDEX["C2"]))[
        config.MACHINE_INDEX["C2"]
    ]
    w_asm = twin.compute_wear(_states_one_hot(run_steps, config.MACHINE_INDEX["ASM1"]))[
        config.MACHINE_INDEX["ASM1"]
    ]
    w_rwk = twin.compute_wear(_states_one_hot(run_steps, config.MACHINE_INDEX["RWK0"]))[
        config.MACHINE_INDEX["RWK0"]
    ]
    np.testing.assert_allclose(w_a, 0.8)
    np.testing.assert_allclose(w_c, 0.8 * 0.7)
    np.testing.assert_allclose(w_asm, 0.8 * 0.5)
    np.testing.assert_allclose(w_rwk, 0.8 * 0.3)


def test_wstate_knee_delayed_on_derated_machine():
    c_idx = config.MACHINE_INDEX["C2"]
    w192 = twin.compute_wear(_states_one_hot(192, c_idx))[c_idx]
    assert w192 < _KNEE
    w_full = twin.compute_wear(_states_one_hot(_T, c_idx))[c_idx]
    assert w_full > _KNEE
    rwk_idx = config.MACHINE_INDEX["RWK0"]
    w_rwk_full = twin.compute_wear(_states_one_hot(_T, rwk_idx))[rwk_idx]
    np.testing.assert_allclose(w_rwk_full, 300 * 0.3 / 240.0)
    assert w_rwk_full < _KNEE


def test_wstate_reset_endpoint_equals_post_reset_accumulation():
    run_idx = config.MACHINE_INDEX["A0"]
    states = _states_one_hot(_T, run_idx)
    w = twin.compute_wear(states, {"A0": {100}})[run_idx]
    suffix = [["STARVED"] * _T for _ in range(_N)]
    suffix[run_idx] = ["RUN"] * 200 + ["STARVED"] * (_T - 200)
    expected = twin.compute_wear(suffix)[run_idx]
    np.testing.assert_allclose(w, expected)
    no_reset = twin.compute_wear(states)[run_idx]
    assert w < no_reset


def test_maint_event_reset_in_episode():
    maint = [{"machine": "A0", "t": 150}]
    rec_reset = twin.run_episode(777, None, maintenance=maint)
    rec_plain = twin.run_episode(777, None)
    idx = config.MACHINE_INDEX["A0"]
    assert rec_reset["wstate"][idx] < rec_plain["wstate"][idx]
    maint_events = [e for e in rec_reset["events"] if e.get("event") == "MAINT_EVENT"]
    assert len(maint_events) == 1
    assert maint_events[0]["machine"] == "A0"
    assert maint_events[0]["t"] == 150
    plain_events = [e for e in rec_plain["events"] if e.get("event") == "MAINT_EVENT"]
    assert plain_events == []


def test_maint_endpoint_matches_wear_after_last_reset():
    maint = [{"machine": "A0", "t": 100}, {"machine": "A0", "t": 200}]
    rec = twin.run_episode(777, None, maintenance=maint)
    idx = config.MACHINE_INDEX["A0"]
    expected = twin.compute_wear(rec["states"], {"A0": {100, 200}})[idx]
    np.testing.assert_allclose(rec["wstate"][idx], expected)
    np.testing.assert_allclose(rec["strat"]["wear_endpoint"], max(rec["wstate"]))


def test_maint_determinism_same_seed_twice_identical():
    maint = [{"machine": "B2", "t": 120}, {"machine": "C6", "t": 200}]
    rec1 = twin.run_episode(777, None, maintenance=maint)
    rec2 = twin.run_episode(777, None, maintenance=maint)
    assert twin.replay_digest(rec1) == twin.replay_digest(rec2)
    assert rec1["wstate"] == rec2["wstate"]
    assert rec1["events"] == rec2["events"]
    assert rec1["strat"]["wstate_per_machine"] == rec2["strat"]["wstate_per_machine"]


def test_maint_default_none_matches_today_behavior():
    rec_plain = twin.run_episode(777, None)
    rec_none = twin.run_episode(777, None, maintenance=None)
    assert twin.replay_digest(rec_plain) == twin.replay_digest(rec_none)
    assert rec_plain["wstate"] == rec_none["wstate"]
    assert rec_plain["strat"]["maint_flag"] is False
    assert rec_none["strat"]["maint_flag_unvalidated"] is True


def test_maint_invalid_raises():
    with pytest.raises(ValueError):
        twin.run_episode(777, None, maintenance=[{"machine": "ZZZ", "t": 10}])
    with pytest.raises(ValueError):
        twin.run_episode(777, None, maintenance=[{"machine": "A0", "t": -1}])
    with pytest.raises(ValueError):
        twin.run_episode(777, None, maintenance=[{"machine": "A0", "t": _T}])
    with pytest.raises(ValueError):
        twin.run_episode(777, None, maintenance=[{"machine": "A0"}])
    with pytest.raises(ValueError):
        twin.run_episode(777, None, maintenance="A0@10")


def test_maint_flag_flip():
    rec_empty = twin.run_episode(777, None, maintenance=[])
    assert rec_empty["strat"]["maint_flag"] is False
    assert rec_empty["strat"]["maint_flag_unvalidated"] is True
    rec_used = twin.run_episode(777, None, maintenance=[{"machine": "A0", "t": 50}])
    assert rec_used["strat"]["maint_flag"] is True
    assert rec_used["strat"]["maint_flag_unvalidated"] is False


def test_wstate_exports_record_strat_parquet(tmp_path):
    rec = twin.run_episode(777, None, maintenance=[{"machine": "A0", "t": 150}])
    assert len(rec["wstate"]) == 26
    assert all(isinstance(v, float) for v in rec["wstate"])
    per_machine = rec["strat"]["wstate_per_machine"]
    assert set(per_machine) == set(config.MACHINE_INDEX)
    for name, idx in config.MACHINE_INDEX.items():
        np.testing.assert_allclose(per_machine[name], rec["wstate"][idx])
    out = tmp_path / "artifacts" / "dataset_v3.parquet"
    dataset_export.export(seed=777, out=out)
    df = dataset_export.load_dataset(out)
    for name in config.MACHINE_INDEX:
        assert f"wstate_{name}" in df.columns, f"Missing parquet column wstate_{name}"
    np.testing.assert_allclose(
        df["wstate_A0"].iloc[0], twin.run_episode(777, None)["wstate"][0]
    )
