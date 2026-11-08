"""Runtime bench tests (latency, throughput, determinism, streaming delay)."""

from __future__ import annotations

import numpy as np
import pandas as pd


def _tiny_artifact(tmp_path):
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
    finalize(df, out_dir=str(tmp_path / "art"), w=16, stride=16, seed=0)
    return str(tmp_path / "art")


def test_bench_reports_latency_throughput_and_delay(tmp_path):
    import numpy as np

    from scripts.bench_windows import bench
    from src.window_dataset import build_windows

    art = _tiny_artifact(tmp_path)
    tiny = pd.DataFrame(
        {
            "episode_id": [9] * 64,
            "step": list(range(64)),
            "y": [0] * 32 + [1] * 32,
            "fault_family": ["none"] * 32 + ["spike"] * 32,
            "obs_A0": np.concatenate([np.zeros(32), np.linspace(0, 8, 32)]),
            "cycle_lag": list(range(64)),
            "stale_hold_run": [0] * 64,
            "reject_flag_count": [0] * 64,
            "degrade_flag_count": [0] * 64,
        }
    )
    sw, sy, sfam, sg = build_windows(tiny, w=16, stride=16)
    r = bench(art, n_windows=64, stream=(sw, sy, sg, sfam))
    assert r["single_ms_p50"] > 0 and r["windows_per_sec"] > 0
    assert r["peak_ram_mb"] > 0 and r["reload_identical"] is True
    assert set(r) >= {
        "single_ms_p50",
        "windows_per_sec",
        "peak_ram_mb",
        "reload_identical",
        "stream_delay_ticks_p50",
    }
