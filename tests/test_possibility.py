"""Possibility engine tests: forward-backward node marginals over DAG neighborhood."""

import pandas as pd


def _line_df(n=300):
    import numpy as np

    rng = np.random.default_rng(0)
    d = {"episode_id": [1] * n, "step": list(range(n))}
    for m in ["A0", "A1", "A2"]:
        d[f"obs_{m}"] = rng.normal(0, 1, size=n)
        d[f"state_{m}"] = ["RUN"] * n
    return pd.DataFrame(d)


def test_neighborhood_restricts_to_one_hop_plus_changed():
    from src.possibility import neighborhood

    edges = {"A0": ["A1"], "A1": ["A2"], "A2": [], "ZZ": []}
    changed = {"A0", "A1", "A2"}
    nb = neighborhood("A1", changed, edges, radius=1)
    assert nb == {"A0", "A1", "A2"}
    nb2 = neighborhood("A1", {"A1"}, edges, radius=1)
    assert nb2 == {"A0", "A1", "A2"}  # 1-up/1-down regardless of change
    nb3 = neighborhood("A1", {"A1", "ZZ"}, edges, radius=1)
    assert "ZZ" not in nb3  # unreachable never included


def test_ranking_prefers_earliest_causal_origin():
    from src.possibility import rank_nodes

    edges = {"A0": ["A1"], "A1": ["A2"], "A2": []}
    evidence = {
        "A0": {"onset": 100, "score": 3.0},
        "A1": {"onset": 102, "score": 5.0},
        "A2": {"onset": 104, "score": 9.0},
    }
    out = rank_nodes(evidence, edges, per_hop=(1, 6))
    assert out["A0"] > out["A1"] > out["A2"]  # loudest victim ranks last
    assert abs(sum(out.values()) - 1.0) < 1e-9


def test_fork_shares_mass_both_branches_ranked():
    from src.possibility import rank_nodes

    edges = {"B2": ["B7P", "B7S"], "B7P": ["B8"], "B7S": ["B8"], "B8": []}
    evidence = {
        "B2": {"onset": 100, "score": 3.0},
        "B7P": {"onset": 102, "score": 4.0},
        "B7S": {"onset": 103, "score": 4.0},
    }
    out = rank_nodes(evidence, edges, per_hop=(1, 6))
    assert out["B2"] > out["B7P"] and out["B2"] > out["B7S"]
    assert abs(out["B7P"] - out["B7S"]) < 0.2  # symmetric branches ~equal


def test_unreachable_change_flagged_independent():
    from src.possibility import rank_nodes

    edges = {"A0": ["A1"], "A1": [], "C0": []}
    evidence = {"A0": {"onset": 100, "score": 3.0}, "C0": {"onset": 150, "score": 8.0}}
    _out, indep = rank_nodes(
        evidence, edges, per_hop=(1, 6), return_independent=True, trigger="A0"
    )
    assert (
        "C0" in indep
    )  # loud but unreachable-from-trigger => independent fault, not victim
