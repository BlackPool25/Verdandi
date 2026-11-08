#!/usr/bin/env python3
"""Runtime bench for the finalized window-GBM (step 3 of ship).

Measures what the suite cannot: single-window latency, batch throughput, peak
RAM, reload determinism, and streaming detection delay (episodes scored window
by window in order; delay = first positive window index - first faulty window
index, converted to ticks via stride). Writes bench.json next to the artifact.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import resource
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import joblib
import numpy as np


def _rss_mb() -> float:
    return float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss) / 1024.0


def apply_thresholds(
    scores: np.ndarray, ep_fam: np.ndarray, thresholds: dict
) -> np.ndarray:
    """Per-episode-family threshold decisions (fallback: global_threshold key)."""
    dec = np.zeros(len(scores), dtype=int)
    for f in sorted(set(ep_fam.tolist())):
        m = ep_fam == f
        thr = thresholds.get(str(f), thresholds.get("__global__", 0.5))
        dec[m] = (scores[m] >= float(thr)).astype(int)
    return dec


def stream_delays(
    dec: np.ndarray, y: np.ndarray, groups: np.ndarray, *, stride: int
) -> list[int]:
    """Per fault episode: detection delay in ticks (0 = onset window)."""
    out = []
    for ep in np.unique(groups):
        m = groups == ep
        yw = y[m]
        first_fault = np.flatnonzero(yw)
        if not len(first_fault):
            continue
        hits = np.flatnonzero(dec[m])
        if len(hits):
            out.append(int((hits[0] - first_fault[0]) * stride))
    return out


def bench(
    artifact_dir: str,
    *,
    n_windows: int = 2000,
    seed: int = 0,
    stream: tuple | None = None,
) -> dict:
    """Load artifact, benchmark, return the metric row (also writes bench.json)."""
    art_dir = pathlib.Path(artifact_dir)
    art = joblib.load(art_dir / "model.joblib")
    model, thr = art["model"], dict(art["thresholds"])
    thr["__global__"] = float(art["global_threshold"])
    w, stride = int(art["w"]), int(art["stride"])
    rng = np.random.default_rng(seed)
    n_feat = int(model.n_features_in_)
    del w
    X = rng.normal(size=(n_windows, n_feat))
    model.predict_proba(X[:8])  # warmup
    ts = []
    for i in range(min(200, n_windows)):
        t0 = time.perf_counter()
        model.predict_proba(X[i : i + 1])
        ts.append((time.perf_counter() - t0) * 1000.0)
    t0 = time.perf_counter()
    p1 = model.predict_proba(X)
    wall = time.perf_counter() - t0
    peak = _rss_mb()
    p2 = joblib.load(art_dir / "model.joblib")["model"].predict_proba(X)
    delays = None
    if stream is not None:
        sw, sy, sg, sfam = stream
        from scripts.train_windows import episode_family

        ef = episode_family(np.asarray(sg), np.asarray(sfam))
        s = np.asarray(
            joblib.load(art_dir / "model.joblib")["model"].predict_proba(sw)[:, 1]
        )
        d = apply_thresholds(s, ef, thr)
        delays = stream_delays(d, np.asarray(sy), np.asarray(sg), stride=stride)
    row = {
        "single_ms_p50": float(np.median(ts)),
        "windows_per_sec": float(n_windows / wall) if wall > 0 else 0.0,
        "peak_ram_mb": float(peak),
        "reload_identical": bool(np.array_equal(p1, p2)),
        "stream_delay_ticks_p50": float(np.median(delays)) if delays else None,
        "stream_delay_ticks_max": int(np.max(delays)) if delays else None,
        "artifact": str(art_dir),
    }
    (art_dir / "bench.json").write_text(json.dumps(row, indent=2))
    return row


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="bench finalized window GBM")
    ap.add_argument("--artifact", default="artifacts/window-gbm-v1")
    ap.add_argument("--n-windows", type=int, default=2000)
    ap.add_argument("--parquet", default="artifacts/m0b_mass_*.parquet")
    ap.add_argument("--no-stream", action="store_true")
    args = ap.parse_args(argv)
    stream = None
    if not args.no_stream:
        import glob as _glob

        import pandas as pd  # type: ignore[import-untyped]

        from src.window_dataset import build_windows

        paths = sorted(_glob.glob(args.parquet))
        df = pd.concat([pd.read_parquet(p) for p in paths], ignore_index=True)
        sw, sy, sfam, sg = build_windows(df, w=32, stride=8)
        stream = (sw, sy, sg, sfam)
    r = bench(args.artifact, n_windows=args.n_windows, stream=stream)
    print(
        f"single={r['single_ms_p50']:.3f}ms batch={r['windows_per_sec']:.0f}/s "
        f"ram={r['peak_ram_mb']:.0f}MB reload_identical={r['reload_identical']} "
        f"delay_p50={r['stream_delay_ticks_p50']} delay_max={r['stream_delay_ticks_max']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
