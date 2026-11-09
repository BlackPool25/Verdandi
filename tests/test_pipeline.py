"""End-to-end diagnosis pipeline (TDD RED)."""

import pandas as pd


def _df():
    import numpy as np

    n = 300
    rng = np.random.default_rng(1)
    d = {
        "episode_id": [1] * n,
        "step": list(range(n)),
        "obs_A0": np.concatenate([rng.normal(0, 1, 160), rng.normal(0, 1, 140) + 6.0]),
        "obs_A1": np.concatenate([rng.normal(0, 1, 200), rng.normal(0, 1, 100) + 6.0]),
        "state_A0": ["RUN"] * 160 + ["DOWN"] * 140,
        "state_A1": ["RUN"] * 200 + ["STARVED"] * 100,
    }
    return pd.DataFrame(d)


def test_pipeline_reports_root_path_and_links():
    from src.diagnose import diagnose_incident
    from src.incidents_store import IncidentStore

    edges = {"A0": ["A1"], "A1": ["A2"], "A2": []}
    store = IncidentStore.memory()
    rep = store_and_report(edges, store)
    assert rep["root"] == "A0"
    assert rep["path"][-1] == "A1"
    assert rep["fault_family"] == "unknown"
    assert len(rep["linked"]) >= 1


def store_and_report(edges, store):
    from src.diagnose import diagnose_incident

    return diagnose_incident(
        _df(),
        ["obs_A0", "obs_A1"],
        trigger=150,
        edges=edges,
        store=store,
        seed=7,
        forecast_fn=lambda root, t_det: [(root, t_det, 0), ("A1", t_det + 4, 1)],
    )
