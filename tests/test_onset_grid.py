"""Grid-pinning tests (W-onsetgrid): delay/onset measured on artifact grid.

Artifact grid: w=128, stride=8 (model card v2; scripts/cache_windows.py:65;
every scripts/eval_*.py). scripts/bench_windows.main hardcoded w=32 (the v1
grid) when rebuilding stream windows — any delay measured through it is on
the wrong grid. The test below pins the stream build to the artifact's own
grid. scripts/evaluate_localize already hardcodes the w128 grid; its test
locks that behavior as evidence.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def _tiny_parquet(tmp_path, n=96, w=16, stride=16):
    cols = {
        "episode_id": [1] * n + [2] * n,
        "step": list(range(n)) * 2,
        "y": [0] * 48 + [1] * 48 + [0] * 48 + [1] * 48,
        "fault_family": ["none"] * 48 + ["delay"] * 48
        + ["none"] * 48 + ["loss"] * 48,
        "obs_A0": np.concatenate([np.zeros(48), np.linspace(0, 8, 48)] * 2),
        "cycle_lag": list(range(n)) * 2,
        "stale_hold_run": [0] * (n * 2),
        "reject_flag_count": [0] * (n * 2),
        "degrade_flag_count": [0] * (n * 2),
    }
    p = tmp_path / "tiny.parquet"
    pd.DataFrame(cols).to_parquet(p, index=False)
    return str(p)


def _tiny_artifact(tmp_path, w=16, stride=16):
    from scripts.finalize_window_model import finalize

    n = 96
    df = pd.DataFrame(
        {
            "episode_id": [1] * n + [2] * n + [3] * n,
            "step": list(range(n)) * 3,
            "y": [0] * 48 + [1] * 48 + [0] * 48 + [1] * 48 + [0] * 48 + [1] * 48,
            "fault_family": ["none"] * 48
            + ["delay"] * 48
            + ["none"] * 48
            + ["loss"] * 48
            + ["none"] * 48
            + ["spike"] * 48,
            "obs_A0": np.concatenate([np.zeros(48), np.linspace(0, 8, 48)] * 3),
            "cycle_lag": list(range(n)) * 3,
            "stale_hold_run": [0] * (n * 3),
            "reject_flag_count": [0] * (n * 3),
            "degrade_flag_count": [0] * (n * 3),
        }
    )
    out = str(tmp_path / "art")
    finalize(df, out_dir=out, w=w, stride=stride, seed=0)
    return out


def test_bench_stream_uses_artifact_grid(tmp_path, monkeypatch):
    """Stream windows must be rebuilt on the artifact's (w, stride)."""
    import scripts.bench_windows as bw
    import src.window_dataset as wd

    art = _tiny_artifact(tmp_path, w=16, stride=8)
    pq = _tiny_parquet(tmp_path)
    seen = {}
    real_build = wd.build_windows

    def spy(df, **kw):
        seen.update(kw)
        return real_build(df, **kw)

    monkeypatch.setattr(wd, "build_windows", spy)
    bw.main(["--artifact", art, "--parquet", pq, "--n-windows", "64"])
    assert seen.get("w") == 16, f"stream built on w={seen.get('w')}, artifact w=16"
    assert seen.get("stride") == 8, f"stream stride={seen.get('stride')}, artifact 8"


def test_evaluate_localize_is_w128_grid():
    """Onset path already on artifact grid (evidence lock, w=128/s=8/center 64)."""
    from scripts.evaluate_localize import _eval_one

    n = 300
    g = pd.DataFrame(
        {
            "cycle_lag": [0] * 100 + list(range(1, 201)),
            "stale_hold_run": [0] * n,
            "down_run": [0] * n,
            **{f"obs_A{i}": np.zeros(n) for i in range(3)},
        }
    )
    nwin = (n - 128) // 8 + 1
    assert nwin == 22
    scores = np.where(np.arange(nwin) >= 5, 0.9, 0.1)
    ow = pd.DataFrame({"score": scores})
    r = {"class": "delay", "t0": 100, "dur": 10}
    fam, base, loc = _eval_one(1, g, ow, r, ["obs_A0", "obs_A1", "obs_A2"])
    assert fam == "delay"
    assert base == abs(5 * 8 + 64 - 100) == 4.0
    assert loc == 0.0


def test_stream_delays_tick_conversion():
    """Delay ticks = window-index gap x stride (grid>)units, not windows."""
    from scripts.bench_windows import stream_delays

    dec = np.array([0, 0, 1, 1])
    y = np.array([0, 0, 1, 1])
    groups = np.array([7, 7, 7, 7])
    assert stream_delays(dec, y, groups, stride=8) == [0]
    assert stream_delays(dec, y, groups, stride=1) == [0]
    dec_late = np.array([0, 0, 0, 1])
    assert stream_delays(dec_late, y, groups, stride=8) == [8]
