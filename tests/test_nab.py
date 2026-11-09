"""NAB-lite event scoring tests."""

from __future__ import annotations


def test_early_hit_scores_more_than_late_hit():
    from src.nab import early_credit

    assert early_credit(0, 20) == 1.0
    assert early_credit(2, 20) > early_credit(15, 20) > 0.0
    assert early_credit(-3, 20) == 0.0


def test_nab_score_rewards_hits_punishes_clean_alarms():
    from src.nab import nab_event_score

    good = nab_event_score([(True, 0, 10)] * 9 + [(False, 0, 10)], 10, 1)
    bad = nab_event_score([(True, 0, 10)] * 5 + [(False, 0, 10)] * 5, 10, 8)
    assert good["score"] > bad["score"]
    assert good["hit_rate"] == 0.9 and bad["clean_fp_rate"] == 0.8
    lowfn = nab_event_score(
        [(True, 0, 10)] * 5 + [(False, 0, 10)] * 5, 10, 0, profile="low-fn"
    )
    assert lowfn["score"] < 0.6  # misses punished double


def test_jitter_changes_grid_phase_but_not_labels():
    import numpy as np

    from src.window_dataset import build_windows
    from tests.test_window_dataset import _df  # type: ignore[import-untyped]

    outs = set()
    for seed in range(5):
        _X, y, _, _, st = build_windows(
            _df(), w=16, stride=8, jitter=8, seed=seed, return_starts=True
        )
        outs.add(int(st[0]))
        assert set(np.unique(y)) <= {0, 1}
    assert len(outs) > 1  # phase actually varies


def test_point_aggregation_localizes_to_covering_windows():
    import numpy as np

    from src.window_dataset import aggregate_to_points

    scores = np.array([0.1, 0.9, 0.1])
    groups = np.array([7, 7, 7])
    starts = np.array([0, 4, 8])
    ps, pg, pt = aggregate_to_points(scores, groups, starts, w=8)
    assert (pg == 7).all() and pt.min() >= 0 and pt.max() < 16
    # Tick 6 is covered by windows [0,8) and [4,12): mean(0.1, 0.9) = 0.5.
    assert abs(float(ps[pt == 6][0]) - 0.5) < 1e-9
    # Tick 0 covered only by the first window.
    assert abs(float(ps[pt == 0][0]) - 0.1) < 1e-9
