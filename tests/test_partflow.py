"""Part-flow block tests: invariant, no machine identity, quality-visible."""

import numpy as np
import pandas as pd


def _ep(n=200, quality_surge_at=None):
    rng = np.random.default_rng(0)
    d = {
        "episode_id": [1] * n,
        "step": list(range(n)),
        "y": [0] * n,
        "fault_family": ["none"] * n,
    }
    for i in range(3):
        d[f"obs_M{i}"] = rng.normal(0, 1, size=n)
    d["funnel_rate"] = np.full(n, 0.13)
    d["scrap_flag"] = np.zeros(n, dtype=int)
    d["rwk_passes"] = np.zeros(n, dtype=int)
    d["buffer_occ"] = np.zeros(n)
    for i in range(3):
        d[f"tputlag_M{i}"] = np.zeros(n)
        d[f"downrun_M{i}"] = np.zeros(n)
    if quality_surge_at is not None:
        d["scrap_flag"][quality_surge_at:] = 1
        d["funnel_rate"][quality_surge_at:] = 0.05
    return pd.DataFrame(d)


def test_partflow_flag_adds_features():
    from src.window_dataset import build_windows

    g = _ep()
    X0, _, _, _ = build_windows(g, w=32, stride=8, invariant=True)
    X1, _, _, _ = build_windows(g, w=32, stride=8, invariant=True, partflow=True)
    assert X1.shape[1] > X0.shape[1]
    assert X1.shape[1] - X0.shape[1] == 10


def test_partflow_fires_on_quality_surge():
    from src.window_dataset import build_windows

    g = _ep(quality_surge_at=150)
    X, _, _, _ = build_windows(g, w=32, stride=8, invariant=True, partflow=True)
    # last windows cover the surge: their part-flow tail must exceed first windows'
    assert float(X[-1, -10:].sum()) > float(X[0, -10:].sum())


def test_partflow_invariant_to_machine_permutation():
    from src.window_dataset import build_windows

    g = _ep(quality_surge_at=150)
    X1, _, _, _ = build_windows(g, w=32, stride=8, invariant=True, partflow=True)
    g2 = g.copy()
    g2 = g2.rename(
        columns={
            "tputlag_M0": "tputlag_M9",
            "tputlag_M1": "tputlag_M0",
            "tputlag_M9": "tputlag_M1",
        }
    )
    X2, _, _, _ = build_windows(g2, w=32, stride=8, invariant=True, partflow=True)
    np.testing.assert_allclose(X1[:, -10:], X2[:, -10:])


def test_anchor_regime_is_episode_prefix():
    import numpy as np

    from src.window_dataset import anchor_regimes_by_episode

    reg = np.array(["RUN", "DOWN", "DOWN", "RUN", "STARVED"])
    grp = np.array([1, 1, 1, 2, 2])
    out = anchor_regimes_by_episode(reg, grp)
    assert list(out) == ["RUN", "RUN", "RUN", "RUN", "RUN"]
