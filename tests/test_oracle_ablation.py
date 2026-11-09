"""Oracle-onset ablation tests: GT onset injection for the 2x2 experiment."""

import numpy as np
import pandas as pd


def _frame(n=300, shift_at=200, seed=0):
    rng = np.random.default_rng(seed)
    d = {
        "episode_id": [1] * n,
        "step": list(range(n)),
        "obs_A0": np.concatenate([rng.normal(0, 1, shift_at), rng.normal(0, 1, n - shift_at) + 6.0]),
        "obs_B9": rng.normal(0, 1, size=n),
        "state_A0": ["RUN"] * n,
        "state_B9": ["RUN"] * n,
    }
    return pd.DataFrame(d)


def test_oracle_onset_overrides_estimate_for_root():
    from src.diagnose import diagnose_multi_origin

    g = _frame()
    est = diagnose_multi_origin(g, ["obs_A0", "obs_B9"])
    est_tick = {r["machine"]: r["onset"] for r in est}["A0"]
    assert est_tick != 150  # estimator fires late on this frame
    ora = diagnose_multi_origin(g, ["obs_A0", "obs_B9"], oracle_onset={"A0": 150})
    got = {r["machine"]: (r["onset"], r["onset_kind"]) for r in ora}
    assert got["A0"][0] == 150
    assert got["A0"][1] == "oracle"


def test_oracle_onset_none_is_default_path():
    from src.diagnose import diagnose_multi_origin

    g = _frame()
    a = diagnose_multi_origin(g, ["obs_A0", "obs_B9"])
    b = diagnose_multi_origin(g, ["obs_A0", "obs_B9"], oracle_onset=None)
    assert [(r["machine"], r["onset"]) for r in a] == [(r["machine"], r["onset"]) for r in b]
