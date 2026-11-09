"""Specialist zoo tests: S6 breakdown, S3 loss, S2 bias (temporal only)."""

import numpy as np
import pandas as pd


def _g(n=300, seed=0):
    rng = np.random.default_rng(seed)
    return pd.DataFrame(
        {
            "episode_id": [1] * n,
            "step": list(range(n)),
            "obs_M": rng.normal(0, 1, size=n),
            "state_M": ["RUN"] * n,
            "tput_M": (rng.random(size=n) < 0.2).astype(int),
        }
    )


def test_s6_fires_on_down_edge_with_dwell():
    from src.specialists import s6_breakdown

    g = _g()
    g.loc[200:, "state_M"] = "DOWN"
    g.loc[200:, "tput_M"] = 0
    out = s6_breakdown(g, "M", trigger=250, W=64, K=5)
    assert out["fires"] is True and abs(out["onset"] - 200) <= 4


def test_s6_quiet_on_microstop():
    from src.specialists import s6_breakdown

    g = _g()
    g.loc[200:201, "state_M"] = "DOWN"  # 2-tick blip < K=5
    out = s6_breakdown(g, "M", trigger=250, W=64, K=5)
    assert out["fires"] is False


def test_s3_fires_on_flatline():
    from src.specialists import s3_loss

    g = _g()
    g.loc[200:, "obs_M"] = 3.0  # frozen value
    out = s3_loss(g, "M", trigger=250, W=64, K=8)
    assert out["fires"] is True and abs(out["onset"] - 200) <= 8


def test_s3_fires_on_intermittent_stale():
    from src.specialists import s3_loss

    g = _g()
    v = g["obs_M"].to_numpy().copy()
    # stale-hold: every 3rd tick repeats the previous value
    for t in range(200, 300, 3):
        v[t] = v[t - 1]
    g["obs_M"] = v
    out = s3_loss(g, "M", trigger=250, W=64, K=8)
    assert out["fires"] is True


def test_s2_fires_on_level_shift():
    from src.specialists import s2_bias

    g = _g()
    g.loc[200:, "obs_M"] += 4.0
    out = s2_bias(g, "M", trigger=250, W=64)
    assert out["fires"] is True and abs(out["onset"] - 200) <= 12


def test_gate_priority_breakdown_over_bias():
    from src.specialists import arbitrate

    votes = [
        {"kind": "bias", "fires": True, "onset": 200, "score": 3.0},
        {"kind": "breakdown", "fires": True, "onset": 202, "score": 9.0},
    ]
    assert arbitrate(votes)["kind"] == "breakdown"
