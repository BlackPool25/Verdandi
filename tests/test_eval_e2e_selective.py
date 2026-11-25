"""Tests for scripts/eval_e2e_selective.py (W-e2e66, Shreyas/PRISSUE-66 follow-up).

Hermetic, CPU-only. The calibrated gate itself is NEVER reimplemented here:
gate behavior goes through the live `src.diagnose.diagnose_incident` with an
injected stub calibrator. Battery reads only happen in the __main__ path,
never in these tests.
"""

import numpy as np
import pandas as pd

import scripts.eval_e2e_selective as sel


def _frame(seed=0, a0_onset=185, b9_onset=195, n=300, fault_step=190):
    rng = np.random.default_rng(seed)
    obs_a0 = np.concatenate(
        [rng.normal(0, 1, a0_onset), rng.normal(0, 1, n - a0_onset) + 8.0]
    )
    obs_b9 = np.concatenate(
        [rng.normal(0, 1, b9_onset), rng.normal(0, 1, n - b9_onset) + 1.0]
    )
    steps = list(range(n))
    return pd.DataFrame(
        {
            "episode_id": [1] * n,
            "step": steps,
            "obs_A0": obs_a0,
            "obs_B9": obs_b9,
            "state_A0": ["RUN"] * a0_onset + ["DOWN"] * (n - a0_onset),
            "state_B9": ["RUN"] * b9_onset + ["STARVED"] * (n - b9_onset),
            "root_id": ["A0"] * n,
            "fault_mask": [1 if s >= fault_step else 0 for s in steps],
            "fault_family": ["breakdown" if s >= fault_step else "none" for s in steps],
        }
    )


EDGES = {"A0": ["B9"], "B9": []}
COLS = ["obs_A0", "obs_B9"]
OPEN = {"T": 1.0, "a": 0.0, "b": 0.0, "tau": float("-inf"), "risk_target": 0.3}
SHUT = {"T": 2.58, "a": 5.0, "b": -3.0, "tau": 2.0, "risk_target": 0.3}


def test_aggregate_selective_metrics():
    outcomes = [
        {"covered": True, "correct": True, "reason": None},
        {"covered": True, "correct": False, "reason": None},
        {"covered": False, "correct": False, "reason": "low-confidence-calibrated"},
        {"covered": False, "correct": False, "reason": "low-recall"},
    ]
    m = sel.aggregate(outcomes)
    assert m["n"] == 4
    assert m["n_covered"] == 2
    assert m["coverage"] == 0.5
    assert m["selective_accuracy"] == 0.5
    assert m["selective_risk"] == 0.5
    assert m["abstain"] == {"low-confidence-calibrated": 1, "low-recall": 1}


def test_aggregate_all_abstain_selective_undefined():
    outcomes = [{"covered": False, "correct": False, "reason": "silent-clean"}]
    m = sel.aggregate(outcomes)
    assert m["coverage"] == 0.0
    assert m["selective_accuracy"] is None
    assert m["selective_risk"] is None


def test_select_trigger_uses_first_fault_tick():
    g = _frame()
    assert sel.select_trigger(g) == 190


def test_select_trigger_none_when_clean():
    g = _frame()
    g["fault_mask"] = 0
    assert sel.select_trigger(g) is None


def test_run_episode_live_gate_open_covers_and_names_root():
    g = _frame()
    out = sel.run_episode(
        g, COLS, EDGES, truth_root="A0", family="breakdown",
        trigger=190, calibrator=dict(OPEN),
    )
    assert out["covered"] is True
    assert out["reason"] is None
    assert out["root"] == "A0"
    assert out["correct"] is True


def test_run_episode_live_gate_shut_abstains_calibrated():
    g = _frame()
    out = sel.run_episode(
        g, COLS, EDGES, truth_root="A0", family="breakdown",
        trigger=190, calibrator=dict(SHUT),
    )
    assert out["covered"] is False
    assert out["reason"] == "low-confidence-calibrated"
    assert out["correct"] is False


def test_default_tau_is_live_served_point():
    assert sel.default_tau() == 0.739
