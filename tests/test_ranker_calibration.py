"""Ranker-calibration helpers (hermetic, synthetic — no artifacts)."""

import numpy as np

import scripts.fit_ranker_calibration as frc


def test_episode_stats_top1_margin_correct():
    # oof_pred is 1-D (one ranker score per candidate row); S stacks per-ep rows.
    oof_pred = np.array([3.0, 1.0, 0.0, 0.5, 2.0, 0.1])
    y = np.array([1, 0, 0, 0, 1, 0])
    groups = np.array([7, 7, 7, 9, 9, 9])
    eps, S, true_idx = frc.episode_stats(oof_pred, y, groups)
    assert eps.tolist() == [7, 9]
    assert S.shape == (2, 3)
    assert true_idx.tolist() == [0, 1]


def test_split_episodes_disjoint_stratified_seedpinned():
    rng = np.random.default_rng(3)
    eps = np.arange(40)
    fam = np.array(["a"] * 20 + ["b"] * 20)
    f1, e1 = frc.split_episodes(eps, fam, seed=0)
    f2, _e2 = frc.split_episodes(eps, fam, seed=0)
    assert sorted(f1.tolist()) == sorted(f2.tolist())
    assert not set(f1.tolist()) & set(e1.tolist())
    assert set(f1.tolist()) | set(e1.tolist()) == set(eps.tolist())
    # stratified: each family split ~half/half
    assert sum(fam[np.isin(eps, e1)] == "a") == 10
    assert sum(fam[np.isin(eps, e1)] == "b") == 10
    assert rng is not None  # silence unused


def test_ep_metrics_gating_math():
    S = np.array([[0.9, 0.1], [0.4, 0.6], [0.8, 0.2], [0.3, 0.7]])
    true = np.array([0, 0, 0, 1])
    conf = np.array([0.95, 0.40, 0.85, 0.90])
    m = frc._ep_metrics(S, true, conf, tau=0.8)
    assert m["forced_top1"] == 0.75  # eps 0,2,3 correct
    assert m["n_covered"] == 3
    assert m["gated_top1"] == 1.0
    assert m["risk"] == 0.0
