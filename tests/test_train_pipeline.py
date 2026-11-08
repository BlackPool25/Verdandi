"""Phase-A pipeline contract tests (M0b-T): stride/purge, weights, focal, thresholds, CLI.

TDD RED: build_windows stride/purge semantics, purge helper, sample weights,
focal weights, threshold hooks, and runtable CLI do not exist yet.
"""

from __future__ import annotations

import csv

import numpy as np
import pandas as pd  # type: ignore[import-untyped]
import pytest

from src import train_pipeline as tp
from src.window_export import prefix_repr

pytestmark = [pytest.mark.k3, pytest.mark.battery]


def _cover(n: int = 40, seed: int = 0) -> dict:
    rng = np.random.default_rng(seed)
    return prefix_repr(rng.normal(size=n))


def test_unresolved_stride_one_emits_all_windows():
    n, w = 40, 8
    df = pd.DataFrame({"episode_id": np.repeat(7, n)})
    out = tp.build_windows(df, _cover(n), w=w)
    assert list(out["t_start"]) == list(range(n - w + 1))
    assert list(out["t_end"]) == list(range(w, n + 1))


def test_purge_embargo_is_exclusion_gap_not_stride():
    n, w = 40, 8
    df = pd.DataFrame({"episode_id": np.repeat(7, n)})
    out = tp.build_windows(df, _cover(n), w=w, purge_embargo=2)
    # Stride stays 1 (consecutive starts); 2 windows excluded at each edge.
    assert list(out["t_start"]) == list(range(2, n - w + 1 - 2))


def test_stride_steps_window_starts():
    n, w = 40, 8
    df = pd.DataFrame({"episode_id": np.repeat(7, n)})
    out = tp.build_windows(df, _cover(n), w=w, stride=2)
    assert list(out["t_start"]) == list(range(0, n - w + 1, 2))


def test_apply_purge_embargo_drops_train_near_test():
    t_starts = np.arange(20)
    train_idx = np.arange(20)
    # Test span covers starts 8..11; embargo 2 kills starts 6..13.
    keep = tp.apply_purge_embargo(train_idx, t_starts, test_start=8, test_end=12, embargo=2)
    assert list(keep) == [0, 1, 2, 3, 4, 5, 14, 15, 16, 17, 18, 19]


def test_compute_sample_weights_balanced_upweights_minority():
    y = np.array([0] * 90 + [1] * 10)
    w = tp.compute_sample_weights(y)
    assert len(w) == len(y)
    assert float(w[y == 1].mean()) > float(w[y == 0].mean())
    assert abs(float(w.mean()) - 1.0) < 1e-9


def test_focal_weights_gamma_zero_is_ones():
    p = np.array([0.9, 0.5, 0.1])
    assert list(tp.focal_confidence_weights(p, gamma=0.0)) == [1.0, 1.0, 1.0]


def test_focal_weights_downweight_easy_examples():
    p = np.array([0.9, 0.5])
    assert list(tp.focal_confidence_weights(p, gamma=2.0)) == pytest.approx([0.01, 0.25])


def test_pick_threshold_max_f1_separates():
    scores = np.array([0.1, 0.2, 0.8, 0.9])
    y = np.array([0, 0, 1, 1])
    thr = tp.pick_threshold_max_f1(scores, y)
    assert 0.2 < thr <= 0.8
    assert tp.compute_raw_pointwise_f1(y, (scores >= thr).astype(int)) == 1.0


def test_per_class_thresholds_keyed_by_class():
    scores = np.array([0.1, 0.8, 0.2, 0.9])
    y = np.array([0, 1, 0, 1])
    classes = np.array(["a", "a", "b", "b"])
    out = tp.pick_per_class_thresholds(scores, y, classes)
    assert set(out) == {"a", "b"}


def test_runtable_row_schema():
    row = tp.build_runtable_row(job="unit", n_windows=10, f1=0.5)
    assert {"run_id", "job", "n_windows", "f1_raw", "wall_seconds"} <= set(row)


def test_cli_writes_runtable_csv(tmp_path):
    out = tmp_path / "runtable.csv"
    rc = tp.main(["--out", str(out), "--job", "unit"])
    assert rc == 0
    with open(out, newline="") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 1 and rows[0]["job"] == "unit"
