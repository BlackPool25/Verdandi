"""Cascade path DP over constrained neighborhood (TDD RED)."""

from src.possibility import best_path


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
