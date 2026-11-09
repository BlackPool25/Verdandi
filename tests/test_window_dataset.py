"""Window-dataset builder tests (max-quality track: supervised windows, not steps)."""

from __future__ import annotations

import numpy as np
import pandas as pd


def _df() -> pd.DataFrame:
    n = 64
    return pd.DataFrame(
        {
            "episode_id": [1] * n,
            "step": list(range(n)),
            "y": [0] * 32 + [1] * 32,
            "fault_family": ["none"] * 32 + ["delay"] * 32,
            "obs_A0": np.concatenate([np.zeros(32), np.linspace(0, 8, 32)]),
            "cycle_lag": list(range(n)),
            "stale_hold_run": [0] * n,
        }
    )


def test_windows_cover_episode_with_labels_and_no_future():
    from src.window_dataset import build_windows

    X, y, fam, groups = build_windows(_df(), w=16, stride=8)
    assert len(X) == len(y) == len(fam) == len(groups)
    assert set(np.unique(y)) <= {0, 1}
    # A window fully before the fault must be clean; one fully inside faulty.
    assert y[0] == 0 and fam[0] == "none"
    assert y[-1] == 1 and fam[-1] == "delay"
    # Feature matrix is finite and has the documented width.
    assert np.isfinite(X).all() and X.shape[1] > 5


def test_window_features_separate_shift():
    from src.window_dataset import build_windows

    X, y, _, _ = build_windows(_df(), w=16, stride=8)
    assert X[y == 1].mean() > X[y == 0].mean()


def test_invariant_width_and_channel_permutation_invariance():
    import numpy as np
    import pandas as pd

    from src.window_dataset import build_windows

    n = 64
    base = {
        "episode_id": [1] * n,
        "step": list(range(n)),
        "y": [0] * 32 + [1] * 32,
        "fault_family": ["none"] * 32 + ["delay"] * 32,
        "obs_A0": np.concatenate([np.zeros(32), np.linspace(0, 8, 32)]),
        "obs_A1": np.zeros(n),
        "cycle_lag": list(range(n)),
        "stale_hold_run": [0] * n,
        "reject_flag_count": [0] * n,
        "degrade_flag_count": [0] * n,
    }
    df = pd.DataFrame(base)
    Xi, _yi, _, _ = build_windows(df, w=16, stride=16, invariant=True)
    assert Xi.shape[1] == 15 + 8 and np.isfinite(Xi).all()
    swapped = df.copy()
    swapped[["obs_A0", "obs_A1"]] = df[["obs_A1", "obs_A0"]].values
    Xs, _, _, _ = build_windows(swapped, w=16, stride=16, invariant=True)
    assert np.array_equal(Xi, Xs)
    Xa, _, _, _ = build_windows(df, w=16, stride=16, invariant=False)
    assert Xa.shape[1] == 2 * 5 + 8  # absolute width scales with channel count
    Xas, _, _, _ = build_windows(swapped, w=16, stride=16, invariant=False)
    assert not np.array_equal(Xa, Xas)  # absolute keys on which channel moved


def test_offset_shifts_grid_phase_without_breaking_labels():
    from src.window_dataset import build_windows

    X0, _y0, _, _ = build_windows(_df(), w=16, stride=8)
    X4, y4, _, _ = build_windows(_df(), w=16, stride=8, offset=4)
    assert len(X4) == len(X0) - 1 or len(X4) == len(X0)
    assert set(np.unique(y4)) <= {0, 1} and y4[0] == 0
    assert not np.array_equal(X0[: len(X4)], X4)


def test_clean_norm_centers_clean_and_preserves_shift():
    from src.window_dataset import apply_norm, fit_clean_norm

    rng = np.random.default_rng(0)
    Xc = rng.normal(10, 2, size=(50, 10))
    Xf = rng.normal(16, 2, size=(10, 10))
    X = np.vstack([Xc, Xf])
    y = np.array([0] * 50 + [1] * 10)
    med, iqr = fit_clean_norm(X, y, n_obs=10)
    Xn = apply_norm(X, med, iqr, n_obs=10)
    assert abs(float(Xn[:50].mean())) < 0.2
    assert float(Xn[50:].mean()) > 2.0


def test_build_jobs_equivalence():
    import numpy as np
    import pandas as pd

    from src.window_dataset import build_windows

    rng = np.random.default_rng(0)
    frames = []
    for ep in range(6):
        n = 200
        d = {
            "episode_id": [ep] * n,
            "step": list(range(n)),
            "y": [0] * n,
            "fault_family": ["none"] * n,
        }
        for i in range(3):
            d[f"obs_M{i}"] = rng.normal(0, 1, size=n)
        d["funnel_rate"] = np.full(n, 0.13)
        d["scrap_flag"] = np.zeros(n, dtype=int)
        d["buffer_occ"] = np.zeros(n)
        for i in range(3):
            d[f"tputlag_M{i}"] = np.zeros(n)
            d[f"downrun_M{i}"] = np.zeros(n)
        frames.append(pd.DataFrame(d))
    df = pd.concat(frames, ignore_index=True)
    kw = {
        "w": 32,
        "stride": 8,
        "invariant": True,
        "jitter": 3,
        "seed": 7,
        "return_starts": True,
    }
    a = build_windows(df, **kw, build_jobs=1)
    b = build_windows(df, **kw, build_jobs=2)
    assert len(a) == len(b) == 5
    np.testing.assert_array_equal(a[3], b[3])  # groups order preserved
    np.testing.assert_allclose(a[0], b[0])
    np.testing.assert_array_equal(a[1], b[1])
    assert list(a[4]) == list(b[4])  # starts identical across backends
