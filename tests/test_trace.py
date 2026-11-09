"""Wavefront tracing tests: sustained STARVED/BLOCKED order, reachability."""

import pandas as pd


def _line(n=300, down_at=150, starves=((1, 152), (2, 155))):
    import numpy as np

    rng = np.random.default_rng(0)
    d = {"episode_id": [1] * n, "step": list(range(n))}
    states = [["RUN"] * n for _ in range(3)]
    for i in range(down_at, n):
        states[0][i] = "DOWN"
    for m, t in starves:
        for i in range(t, n):
            states[m][i] = "STARVED"
    for m in range(3):
        d[f"state_M{m}"] = states[m]
        d[f"obs_M{m}"] = rng.normal(0, 1, size=n)
    return pd.DataFrame(d)


def test_wavefront_orders_downstream():
    from src.trace import wavefront

    out = wavefront(_line(), ["M0", "M1", "M2"])
    assert out["root"] == "M0"
    assert [f["machine"] for f in out["frontier"]] == ["M1", "M2"]
    assert out["frontier"][0]["tick"] < out["frontier"][1]["tick"]


def test_wavefront_ignores_single_tick_blip():
    from src.trace import wavefront

    g = _line()
    g.loc[50, "state_M1"] = "STARVED"  # 1-tick blip, must not rank
    out = wavefront(g, ["M0", "M1", "M2"])
    assert all(f["machine"] != "M1" or f["tick"] != 50 for f in out["frontier"])
    assert out["root"] == "M0"


def test_reachable_respects_topology():
    from src.trace import reachable

    assert reachable("B2", "B7P") is True
    assert reachable("B2", "B7S") is True
    assert reachable("A0", "C7") is False
