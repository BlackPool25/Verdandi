"""Cascade path DP over constrained neighborhood (TDD RED)."""

from src.possibility import best_path


def test_best_cause_path_chain():
    from src.possibility import best_cause_path

    edges = {"A0": ["A1"], "A1": ["A2"], "A2": []}
    ev = {
        "A0": {"onset": 100, "score": 1.0},
        "A1": {"onset": 102, "score": 0.5},
        "A2": {"onset": 104, "score": 0.2},
    }
    path, val, values = best_cause_path(ev, edges, anchor="A2")
    assert path == ["A0", "A1", "A2"]
    assert set(values) == {"A0", "A1", "A2"}


def test_best_cause_path_fork():
    from src.possibility import best_cause_path

    edges = {"B2": ["B7P", "B7S"], "B7P": ["B8"], "B7S": ["B8"], "B8": []}
    ev = {
        "B2": {"onset": 100, "score": 1.0},
        "B7P": {"onset": 102, "score": 0.5},
        "B7S": {"onset": 103, "score": 0.1},
        "B8": {"onset": 105, "score": 0.2},
    }
    path, _, _ = best_cause_path(ev, edges, anchor="B8")
    assert path == ["B2", "B7P", "B8"]


def test_best_cause_path_prunes_inconsistent_edge():
    from src.possibility import best_cause_path

    edges = {"A0": ["A1"], "A1": []}
    ev = {
        "A0": {"onset": 100, "score": 1.0},
        "A1": {"onset": 200, "score": 0.5},  # dt=100 >> hi: not causal
    }
    path, _, _ = best_cause_path(ev, edges, anchor="A1")
    assert path == ["A1"]


def test_best_path_single_chain():
    edges = {"A0": ["A1"], "A1": ["A2"], "A2": []}
    scores = {"A0": 0.6, "A1": 0.3, "A2": 0.1}
    path, prob = best_path(scores, edges, anchor="A2", max_len=3)
    assert path[0] in ("A0", "A1") and path[-1] == "A2"
    assert 0.0 < prob <= 1.0


def test_best_path_fork_prefers_stronger_branch():
    edges = {"B2": ["B7P", "B7S"], "B7P": ["B8"], "B7S": ["B8"], "B8": []}
    scores = {"B2": 0.5, "B7P": 0.3, "B7S": 0.1, "B8": 0.1}
    path, prob = best_path(scores, edges, anchor="B8", max_len=3)
    assert path == ["B2", "B7P", "B8"]
    assert 0.0 < prob <= 1.0
