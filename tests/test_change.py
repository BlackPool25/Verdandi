"""Window change tests: BASE vs RECENT two-sample + CUSUM onset + persistence."""

import numpy as np
import pandas as pd


def _df(n=300, shift_at=200, shift=5.0, seed=0):
    rng = np.random.default_rng(seed)
    return pd.DataFrame(
        {
            "episode_id": [1] * n,
            "step": list(range(n)),
            "obs_M": np.concatenate(
                [rng.normal(0, 1, shift_at), rng.normal(0, 1, n - shift_at) + shift]
            ),
            "state_M": ["RUN"] * shift_at + ["DOWN"] * (n - shift_at)
            if shift_at < n and shift != 0
            else ["RUN"] * n,
        }
    )


def test_change_score_separates_shift_from_clean():
    from src.change import analyze_window

    hot = analyze_window(_df(), "M", trigger=250, W=64)
    cold = analyze_window(_df(shift=0.0), "M", trigger=250, W=64)
    assert hot["score"] > cold["score"] + 1.0
    assert hot["persisted"] is True and cold["persisted"] is False


def test_change_onset_matches_true_tick():
    from src.change import analyze_window

    out = analyze_window(_df(), "M", trigger=250, W=64)
    assert out["onset"] is not None and abs(out["onset"] - 200) <= 8


def test_change_uses_recent_not_single_tick():
    from src.change import analyze_window

    g = _df()
    g.loc[190, "obs_M"] += 30.0  # single-tick spike inside BASE: must not decide
    out = analyze_window(g, "M", trigger=250, W=64)
    assert out["persisted"] is True and abs(out["onset"] - 200) <= 8
