"""Per-regime normalization tests: RUN/STARVED/BLOCKED/DOWN clean baselines."""

import numpy as np


def _framed():
    rng = np.random.default_rng(0)
    Xc = np.vstack([rng.normal(10, 2, size=(50, 4)), rng.normal(-20, 2, size=(50, 4))])
    y = np.array([0] * 100)
    reg = np.array(["RUN"] * 50 + ["STARVED"] * 50)
    return Xc, y, reg


def test_regime_norm_centers_each_regime():
    from src.window_dataset import apply_norm_regime, fit_clean_norm_regime

    Xc, y, reg = _framed()
    table = fit_clean_norm_regime(Xc, y, reg, n_obs=4)
    Xn = apply_norm_regime(Xc, table, reg, n_obs=4, fallback="global")
    assert abs(float(Xn[:50].mean())) < 0.3
    assert abs(float(Xn[50:].mean())) < 0.3


def test_regime_norm_unknown_regime_falls_back():
    from src.window_dataset import apply_norm_regime, fit_clean_norm_regime

    Xc, y, reg = _framed()
    table = fit_clean_norm_regime(Xc, y, reg, n_obs=4)
    Xn = apply_norm_regime(Xc, table, np.array(["DOWN"] * 100), n_obs=4, fallback="global")
    assert np.isfinite(Xn).all()


def test_build_windows_emits_regimes_on_request():
    import pandas as pd

    from src.window_dataset import build_windows

    n = 64
    df = pd.DataFrame(
        {
            "episode_id": [1] * n,
            "step": list(range(n)),
            "y": [0] * n,
            "fault_family": ["none"] * n,
            "obs_A0": np.zeros(n),
            "state_A0": ["RUN"] * 32 + ["STARVED"] * 32,
            "state_A1": ["RUN"] * n,
        }
    )
    out = build_windows(df, w=16, stride=16, return_regimes=True)
    X, _y, _fam, _grp, reg = out
    assert len(reg) == len(X)
    assert set(np.unique(reg)) <= {"RUN", "STARVED", "BLOCKED", "DOWN"}
