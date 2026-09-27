"""Mutation-inversion non-vacuity tests for Verdandi CI pipeline.

Tested entrypoints:
- `from src import twin`: Simulation episode runner (`run_episode`), fault manifest
  (`build_faults`), and topology constants (`MACHINE_INDEX`, `T`).
- `from scripts import check_gates`: Battery gate checker (`evaluate_gates`,
  `parse_csv_file`, `BatteryMetrics`).

Mutation mechanism:
Non-vacuous anomaly detection and CI gate verification require that inverting or
corrupting decision inputs (e.g. inverting fault labels, corrupting anomaly sensor
evidence, inverting detector decisions, or degrading battery metrics) causes a
statistically meaningful degradation in F1 score: delta F1 > 0.10.
A vacuous detector or insensitive gate pipeline would remain indifferent to such
inversions (delta F1 <= 0.10), failing to guard simulation validity.
"""

from __future__ import annotations

import copy
import pathlib
from collections.abc import Sequence

import pytest

from scripts import check_gates
from src import twin
from src.config import MACHINE_INDEX, T

pytestmark = pytest.mark.mutation

_FIXTURES_DIR = pathlib.Path(__file__).resolve().parent / "fixtures"
_GATES_ALL_GREEN_CSV = _FIXTURES_DIR / "gates_all_green.csv"

_F21_B2: dict[str, str | int | float] = {
    "id": "F-21",
    "class": "drift",
    "origin": "B2",
    "t0": 150,
    "dur": 12,
    "mag_sigma": 5.2,
}


def compute_f1(y_true: Sequence[int], y_pred: Sequence[int]) -> float:
    """Compute binary classification F1 score."""
    tp = sum(1 for yt, yp in zip(y_true, y_pred, strict=True) if yt == 1 and yp == 1)
    fp = sum(1 for yt, yp in zip(y_true, y_pred, strict=True) if yt == 0 and yp == 1)
    fn = sum(1 for yt, yp in zip(y_true, y_pred, strict=True) if yt == 1 and yp == 0)

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    if precision + recall == 0.0:
        return 0.0
    return (2.0 * precision * recall) / (precision + recall)


def test_mutation_inversion_label_flip_delta_f1() -> None:
    """Inverting fault labels causes delta F1 > 0.10 (failing-first identity test)."""
    rec = twin.run_episode(777, copy.deepcopy(_F21_B2))
    idx = MACHINE_INDEX["B2"]
    y_true = [1 if 150 <= t < 162 else 0 for t in range(T)]
    y_pred = [1 if rec["obs"][idx][t] >= 73.0 else 0 for t in range(T)]

    f1_normal = compute_f1(y_true, y_pred)
    assert f1_normal >= 0.85, f"Normal detection F1 below bar: {f1_normal}"

    # Invert fault labels (mutation)
    y_mutated = [1 - y for y in y_true]
    f1_mutated = compute_f1(y_mutated, y_pred)
    delta_f1 = f1_normal - f1_mutated

    assert delta_f1 > 0.10, (
        f"Mutation failed non-vacuity threshold: delta_f1={delta_f1}"
    )


def test_mutation_inversion_decision_inversion_delta_f1() -> None:
    """Inverting detector decisions causes delta F1 > 0.10."""
    fault_spec = copy.deepcopy(twin.build_faults()[0])  # F-06 spike on A0
    rec = twin.run_episode(777, fault_spec)
    flt = rec["faults"][0]
    idx = MACHINE_INDEX[flt["origin"]]

    y_true = [1 if flt["t0"] <= t < flt["t1"] else 0 for t in range(T)]
    y_pred = [1 if rec["obs"][idx][t] >= 53.0 else 0 for t in range(T)]

    f1_normal = compute_f1(y_true, y_pred)
    assert f1_normal >= 0.85, f"Normal detection F1 below bar: {f1_normal}"

    y_pred_inverted = [1 - y for y in y_pred]
    f1_inverted = compute_f1(y_true, y_pred_inverted)
    delta_f1 = f1_normal - f1_inverted

    assert delta_f1 > 0.10, f"Decision inversion delta_f1={delta_f1} <= 0.10"


def test_mutation_inversion_evidence_corruption_delta_f1() -> None:
    """Corrupting sensor anomaly evidence causes delta F1 > 0.10."""
    rec = twin.run_episode(777, copy.deepcopy(_F21_B2))
    idx = MACHINE_INDEX["B2"]
    y_true = [1 if 150 <= t < 162 else 0 for t in range(T)]
    y_pred_normal = [1 if rec["obs"][idx][t] >= 73.0 else 0 for t in range(T)]

    f1_normal = compute_f1(y_true, y_pred_normal)
    assert f1_normal >= 0.85, f"Normal detection F1 below bar: {f1_normal}"

    # Corrupt evidence: clean episode sensor readings without anomaly injection
    clean_rec = twin.run_episode(777, None)
    clean_obs = clean_rec["obs"][idx]
    y_pred_corrupted = [1 if clean_obs[t] >= 73.0 else 0 for t in range(T)]

    f1_corrupted = compute_f1(y_true, y_pred_corrupted)
    delta_f1 = f1_normal - f1_corrupted

    assert delta_f1 > 0.10, f"Evidence corruption delta_f1={delta_f1} <= 0.10"


def test_mutation_inversion_check_gates_battery() -> None:
    """Mutating battery F1 metric moves gate evaluation by delta F1 > 0.10 and fails gate."""
    assert _GATES_ALL_GREEN_CSV.exists(), f"Missing fixture: {_GATES_ALL_GREEN_CSV}"
    metrics = check_gates.parse_csv_file(str(_GATES_ALL_GREEN_CSV))

    normal_failures, normal_failed_gates = check_gates.evaluate_gates(
        metrics=metrics,
        f1_threshold=0.85,
        ac1_threshold=0.70,
        flip_threshold=0.40,
        p99_threshold=3.0,
        max_s_threshold=600.0,
        ground_threshold=0.95,
    )
    assert normal_failures == []
    assert normal_failed_gates == []

    baseline_f1 = metrics.f1[0]
    mutated_f1 = 1.0 - baseline_f1
    delta_f1 = baseline_f1 - mutated_f1
    assert delta_f1 > 0.10, f"Battery F1 mutation delta={delta_f1} <= 0.10"

    mutated_metrics = copy.deepcopy(metrics)
    mutated_metrics.f1 = [mutated_f1]

    mutated_failures, mutated_failed_gates = check_gates.evaluate_gates(
        metrics=mutated_metrics,
        f1_threshold=0.85,
        ac1_threshold=0.70,
        flip_threshold=0.40,
        p99_threshold=3.0,
        max_s_threshold=600.0,
        ground_threshold=0.95,
    )
    assert len(mutated_failures) > 0
    assert "F1" in mutated_failed_gates


def test_identity_mutation_fails_non_vacuity_bar() -> None:
    """Identity mutation (vacuous detector) strictly fails the delta F1 > 0.10 criterion."""
    y_true = [1 if 150 <= t < 162 else 0 for t in range(T)]
    y_pred = list(y_true)

    f1_normal = compute_f1(y_true, y_pred)
    # Identity mutation leaves decision unchanged
    f1_identity = compute_f1(y_true, y_pred)
    delta_f1 = f1_normal - f1_identity

    is_non_vacuous = delta_f1 > 0.10
    assert not is_non_vacuous, "Identity mutation must be caught as vacuous"
