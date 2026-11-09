"""Incident report breakdown (TDD RED)."""

from src.report import build_report


def test_report_breakdown_shape():
    edges = {"A0": ["A1"], "A1": ["A2"], "A2": []}
    scores = {"A0": 0.6, "A1": 0.3, "A2": 0.1}
    forecast = [("A0", 100, 0), ("A1", 104, 1), ("A2", 108, 2)]
    meta = {
        "A0": {"onset": 100, "own_state": "DOWN", "metrics": [("obs_A0", 6.2)]},
        "A1": {"onset": 104, "own_state": "STARVED", "metrics": [("obs_A1", 4.1)]},
        "A2": {"onset": 108, "own_state": "STARVED", "metrics": [("obs_A2", 3.3)]},
    }
    rep = build_report(
        root="A0", fault_family="breakdown", scores=scores, edges=edges,
        anchor="A2", forecast=forecast, meta=meta, linked=[("A1", 104), ("A2", 108)],
    )
    assert rep["path"] == ["A0", "A1", "A2"]
    assert rep["nodes"][0]["machine"] == "A0"
    assert "upstream" in rep and "downstream" in rep and "linked" in rep
    assert rep["linked"] == [("A1", 104), ("A2", 108)]
