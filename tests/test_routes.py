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


def test_distant_weak_link_ranks_below_singleton():
    # Soft semantics: far-delayed links are discounted, not vetoed.
    # A diluted 2-hop path must lose to the bare anchor on its own score.
    from src.possibility import upstream_paths

    edges = {"A0": ["A1"], "A1": []}
    ev = {
        "A0": {"onset": 100, "score": 0.9},
        "A1": {"onset": 200, "score": 0.5},  # dt=100: weak transmission
    }
    paths = upstream_paths(ev, edges, anchor="A1", tau=0.1)
    assert paths[0][0] == ["A1"]  # diluted extension loses to the anchor alone


def test_weak_edge_dilutes_path_score():
    from src.possibility import upstream_paths

    edges = {"A0": ["A1"], "A1": ["A2"], "A2": []}
    strong = {
        "A0": {"onset": 100, "score": 0.8},
        "A1": {"onset": 102, "score": 0.5},
        "A2": {"onset": 104, "score": 0.5},
    }
    weak = {
        "A0": {"onset": 100, "score": 0.8},
        "A1": {"onset": 160, "score": 0.5},  # 60-tick lag: weak transmission
        "A2": {"onset": 162, "score": 0.5},
    }
    ps = upstream_paths(strong, edges, anchor="A2", tau=0.1)
    pw = upstream_paths(weak, edges, anchor="A2", tau=0.1)
    full_s = [v for p, v in ps if p[0] == "A0"][0]
    full_w = [v for p, v in pw if p[0] == "A0"][0]
    assert full_s > full_w  # same nodes, weak edge dilutes


def test_stronger_root_wins_despite_dilution():
    from src.possibility import upstream_paths

    edges = {"A0": ["A1"], "A1": ["A2"], "D0": ["A2"], "A2": []}
    ev = {
        "A0": {"onset": 100, "score": 0.9},
        "A1": {"onset": 170, "score": 0.2},  # badly mistimed middle: dilutes hard
        "D0": {"onset": 100, "score": 0.5},
        "A2": {"onset": 104, "score": 0.4},
    }
    paths = upstream_paths(ev, edges, anchor="A2", tau=0.1, max_len=3)
    assert len(paths) >= 2
    assert paths[0][0][0] == "D0"  # coherent short path beats diluted long one


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


def _chain_ev():
    return {
        "A0": {"onset": 100, "score": 0.8},
        "A1": {"onset": 102, "score": 0.5},
        "A2": {"onset": 104, "score": 0.4},
    }


def _chain_edges():
    return {"A0": ["A1"], "A1": ["A2"], "A2": []}


def test_upstream_deterministic_across_runs():
    from src.possibility import upstream_paths

    a = upstream_paths(_chain_ev(), _chain_edges(), anchor="A2")
    b = upstream_paths(_chain_ev(), _chain_edges(), anchor="A2")
    assert a == b


def test_upstream_respects_max_len():
    from src.possibility import upstream_paths

    paths = upstream_paths(_chain_ev(), _chain_edges(), anchor="A2", max_len=2)
    assert all(len(p) <= 2 for p, _ in paths)
    paths3 = upstream_paths(_chain_ev(), _chain_edges(), anchor="A2", max_len=3)
    assert any(len(p) == 3 for p, _ in paths3)


def test_upstream_missing_anchor_falls_back():
    from src.possibility import upstream_paths

    assert upstream_paths(_chain_ev(), _chain_edges(), anchor="ZZ") == [(["ZZ"], 1.0)]


def test_upstream_tau_boundary():
    from src.possibility import upstream_paths

    ev = {
        "A0": {"onset": 100, "score": 0.1},
        "A1": {"onset": 102, "score": 0.5},
        "A2": {"onset": 104, "score": 0.4},
    }
    at = upstream_paths(ev, _chain_edges(), anchor="A2", tau=0.1)
    below = upstream_paths(ev, _chain_edges(), anchor="A2", tau=0.100001)
    assert any("A0" in p for p, _ in at)
    assert all("A0" not in p for p, _ in below)


def test_upstream_probs_sum_to_one():
    from src.possibility import upstream_paths

    paths = upstream_paths(_chain_ev(), _chain_edges(), anchor="A2")
    assert abs(sum(v for _, v in paths) - 1.0) < 1e-9


def test_upstream_order_independent_dict_insertion():
    from src.possibility import upstream_paths

    ev = {
        "A0": {"onset": 100, "score": 0.8},
        "A1": {"onset": 102, "score": 0.5},
        "A2": {"onset": 104, "score": 0.4},
    }
    e1 = {"A0": ["A1"], "A1": ["A2"], "A2": []}
    e2 = {"A2": [], "A1": ["A2"], "A0": ["A1"]}
    assert upstream_paths(ev, e1, anchor="A2") == upstream_paths(ev, e2, anchor="A2")
