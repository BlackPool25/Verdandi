"""Flow window features: causality + shape."""

import numpy as np
import pandas as pd


def _df(n=300, seed=0):
    rng = np.random.default_rng(seed)
    d = {"episode_id": [1] * n, "step": list(range(n))}
    for m in ("A0", "B7P"):
        d[f"obs_{m}"] = rng.normal(0, 1, n)
    d["buffer_0"] = np.concatenate([np.zeros(150), np.ones(n - 150) * 5])
    d["sunk"] = np.arange(n, dtype=float)
    return pd.DataFrame(d)


def test_flow_features_shape_and_causality():
    from src.flow_features import build_flow_features

    df = _df()
    groups = np.array([1] * 10)
    starts = np.array([16 * i for i in range(10)])
    X = build_flow_features(df, groups, starts, w=128)
    assert X.shape == (10, 2 * 2)  # buffer_0 + sunk
    # causality: masking the future must not change already-emitted rows
    df2 = df.copy()
    df2.loc[df2["step"] >= 200, "buffer_0"] = 999.0
    X2 = build_flow_features(df2, groups, starts, w=128)
    n = int((200 / 16))
    assert np.array_equal(X[:n], X2[:n])


def test_flow_features_parallel_matches_serial():
    import pandas as pd

    from src.flow_features import build_flow_features

    df = _df()
    df["episode_id"] = [1] * 150 + [2] * 150
    groups = np.array([1] * 10 + [2] * 10)
    starts = np.array([16 * i for i in range(10)] * 2)
    a = build_flow_features(df, groups, starts, w=128, jobs=1)
    b = build_flow_features(df, groups, starts, w=128, jobs=2)
    assert np.array_equal(a, b)


def test_flow_features_fire_on_buffer_shift():
    from src.flow_features import build_flow_features

    df = _df()
    groups = np.array([1] * 12)
    starts = np.array([16 * i for i in range(12)])
    X = build_flow_features(df, groups, starts, w=128)
    # buffer_0 mean (col 0) jumps after step 150
    assert X[:, 0].max() > X[:, 0].min() + 1.0
