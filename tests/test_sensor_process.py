"""D2 combine tests: machine-agnostic sensor-vs-process, staged with kill-bars."""

import numpy as np
import pandas as pd


def _ep(n=300, kind="bias", seed=0):
    rng = np.random.default_rng(seed)
    d = {"episode_id": [1] * n, "step": list(range(n))}
    obs = rng.normal(0, 1, size=n)
    if kind == "bias":
        obs[150:] += 5.0
    elif kind == "stuck":
        obs[150:] = obs[149]
    d["obs_M"] = obs
    d["state_M"] = ["RUN"] * n
    d["buffer_occ"] = np.zeros(n)
    d["degrade_flag_count"] = np.zeros(n, dtype=int)
    d["reject_flag_count"] = np.zeros(n, dtype=int)
    return pd.DataFrame(d)


def test_shape_veto_catches_stuck_as_sensor():
    from src.sensor_process import shape_veto

    out = shape_veto(_ep(kind="stuck"), "M")
    assert out == "sensor"
    assert shape_veto(_ep(kind="bias"), "M") is None


def test_quality_lift_flags_process():
    from src.sensor_process import quality_lift

    g = _ep(kind="bias")
    g.loc[200:, "reject_flag_count"] = 1
    assert quality_lift(g) is True
    assert quality_lift(_ep(kind="bias")) is False


def test_combine_bias_is_sensor_without_parts_or_wip():
    from src.sensor_process import decide

    out = decide(_ep(kind="bias"), ["M"], trigger=160)
    assert out["verdict"] == "sensor"
    assert out["stage"] in ("coordination", "shape")


def test_combine_abstains_without_evidence():
    from src.sensor_process import decide

    n = 300
    rng = np.random.default_rng(9)
    g = pd.DataFrame(
        {
            "episode_id": [1] * n,
            "step": list(range(n)),
            "obs_M": rng.normal(0, 1, size=n),
            "state_M": ["RUN"] * n,
            "buffer_occ": np.zeros(n),
            "degrade_flag_count": np.zeros(n, dtype=int),
            "reject_flag_count": np.zeros(n, dtype=int),
        }
    )
    out = decide(g, ["M"], trigger=160)
    assert out["verdict"] in ("sensor", "abstain")
