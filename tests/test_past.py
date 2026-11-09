"""PAST card tests: trajectory-only change capture, no snapshots."""

import numpy as np
import pandas as pd


def _g():
    n = 300
    rng = np.random.default_rng(0)
    d = {
        "episode_id": [1] * n,
        "step": list(range(n)),
        "obs_A0": np.concatenate([rng.normal(0, 1, 200), rng.normal(0, 1, 100) + 5.0]),
        "state_A0": ["RUN"] * 200 + ["DOWN"] * 100,
        "tputlag_A0": [0] * 300,
        "downrun_A0": [0] * 200 + list(range(1, 101)),
    }
    return pd.DataFrame(d)


def test_past_card_finds_down_shift():
    from src.past import build_past_card

    card = build_past_card(_g(), "A0", trigger=210, W=64)
    assert card["machine"] == "A0"
    assert card["tau"] is not None and abs(card["tau"] - 200) <= 8
    assert card["persistent"] is True
    assert card["state_delta"] > 0.1
    assert card["dwell_collapse"] > 0.25


def test_past_card_clean_is_quiet():
    from src.past import build_past_card

    n = 300
    rng = np.random.default_rng(1)
    g = pd.DataFrame(
        {
            "episode_id": [1] * n,
            "step": list(range(n)),
            "obs_A0": rng.normal(0, 1, size=n),
            "state_A0": ["RUN"] * n,
            "tputlag_A0": [0] * n,
            "downrun_A0": [0] * n,
        }
    )
    card = build_past_card(g, "A0", trigger=250, W=64)
    assert card["persistent"] is False
    assert card["tau"] is None
