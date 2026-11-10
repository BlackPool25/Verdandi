"""Route-level attribution: k-best paths + ground-truth route extraction (TDD RED)."""

import pandas as pd


def _edges():
    return {"A0": ["A1"], "A1": ["A2"], "D0": ["B1"], "B1": ["A2"], "A2": []}


def test_kbest_returns_multiple_ranked_paths():
    from src.possibility import kbest_paths

    edges = {"A0": ["A1"], "A1": ["A2"], "D0": ["B1"], "B1": ["A2"], "A2": []}
    ev = {
        "A0": {"onset": 100, "score": 0.9},
        "A1": {"onset": 102, "score": 0.5},
        "D0": {"onset": 100, "score": 0.8},
        "B1": {"onset": 103, "score": 0.4},
        "A2": {"onset": 105, "score": 0.2},
    }
    paths = kbest_paths(ev, edges, anchor="A2", k=2)
    assert len(paths) == 2
    assert all(p[-1] == "A2" for p, _ in paths)
    assert paths[0][0] != paths[1][0]  # distinct roots, distinct hypotheses
    assert paths[0][1] >= paths[1][1]  # ranked


def test_kbest_paths_stops_at_unaffected_node():
    from src.possibility import upstream_paths

    edges = {"A0": ["A1"], "A1": ["A2"], "A2": []}
    ev = {
        "A0": {"onset": 100, "score": 0.02},  # below tau: unaffected
        "A1": {"onset": 102, "score": 0.5},
        "A2": {"onset": 104, "score": 0.3},
    }
    paths = upstream_paths(ev, edges, anchor="A2", tau=0.1)
    assert all("A0" not in p for p, _ in paths)  # weak node never extends a path


def test_route_extraction_follows_onset_order_on_dag():
    from src.route import extract_route

    df = pd.DataFrame({
        "episode_id": [1] * 12,
        "step": list(range(12)),
        "state_A0": ["RUN"] * 2 + ["DOWN"] * 10,
        "state_A1": ["RUN"] * 4 + ["STARVED"] * 8,
        "state_A2": ["RUN"] * 6 + ["STARVED"] * 6,
        "state_D0": ["RUN"] * 12,
        "state_B1": ["RUN"] * 12,
    })
    route = extract_route(df, root="A0", edges=_edges())
    assert route[0] == "A0" and route[-1] == "A2"
    assert "D0" not in route and "B1" not in route  # silent branch excluded
