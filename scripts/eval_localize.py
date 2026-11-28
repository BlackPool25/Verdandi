#!/usr/bin/env python3
"""Canonical onset/delay measurement on the artifact's own grid (W-onsetgrid).

Streaming detection delay measured on w=128/stride-8 windows — the shipped
detector grid (model card v2; scripts/cache_windows.py:65). The old headline
("Streaming delay p50 0 ticks") came through scripts/bench_windows.main,
which rebuilt the stream at hardcoded w=32 (the v1 grid) — wrong grid, now
superseded (see docs/DIAGNOSIS_QUALITY.md grid audit).

Method (mirrors scripts/finalize_window_model.py:64-90, split rule :68-69):
seed-pinned HistGBM + sigmoid calibration trained on 2/3 of episodes from the
frozen w128 window cache, per-family tuned thresholds on the held-out third,
delays reported on that same held-out third (validation-optimistic, disclosed
— same posture as finalize's val window-F1). Headline operating point is the
locked global 0.8/k1 (model card); tuned/global-0.5 rows are context.

Lineage is printed with every number (n/seed/split/grid).
"""

from __future__ import annotations

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import numpy as np

W, STRIDE = 128, 8  # artifact grid; asserted against the cache below


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="streaming delay on artifact grid")
    ap.add_argument("--cache", default="artifacts/window_cache")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--max-eps", type=int, default=0,
                    help="cap held-out episodes (0 = all; smoke-test only)")
    args = ap.parse_args(argv)

    import pandas as pd  # type: ignore[import-untyped]

    from scripts.train_windows import (episode_family,  # noqa: E402
                                         pick_per_family_thresholds)
    from src.train_pipeline import pick_threshold_max_f1  # noqa: E402
    from src.window_dataset import apply_norm, fit_clean_norm  # noqa: E402

    cache = pathlib.Path(args.cache)
    meta = pd.read_parquet(cache / "meta.parquet")
    X = np.load(cache / "X_invariant.npy", mmap_mode="r")
    y = meta["y"].to_numpy()
    groups = meta["ep"].to_numpy()
    starts = meta["start"].to_numpy()

    # Grid integrity: cache must be the w128/stride-8 artifact grid.
    steps = np.diff(np.sort(np.unique(starts)))
    assert steps.size and steps.min() == steps.max() == STRIDE, (
        f"cache stride != {STRIDE}: {np.unique(steps)}"
    )
    assert int(starts.max()) + W <= 300, f"starts overflow T=300 for w={W}"
    print(f"grid w={W} stride={STRIDE} (asserted on cache; "
          f"builder lineage scripts/cache_windows.py:64-66)", flush=True)

    eps = sorted(pd.unique(groups))
    n_obs = 15  # invariant features (finalize_window_model.py:71)
    cal_eps = set(eps[2::3])  # finalize split rule (:68-69), NOT fam-stratified
    cal = np.array([e in cal_eps for e in groups])
    Xn = np.asarray(X[~cal], dtype=np.float64)
    yn = y[~cal]
    med, iqr = fit_clean_norm(Xn, yn, n_obs)
    Xc = apply_norm(np.asarray(X[cal], dtype=np.float64), med, iqr, n_obs)

    from sklearn.calibration import CalibratedClassifierCV  # type: ignore[import-untyped]
    from sklearn.ensemble import HistGradientBoostingClassifier  # type: ignore[import-untyped]

    base = HistGradientBoostingClassifier(max_iter=300, random_state=args.seed)
    model = CalibratedClassifierCV(estimator=base, cv=3, method="sigmoid")
    model.fit(Xn, yn)
    from scripts.bench_windows import stream_delays  # noqa: E402

    scores = np.asarray(model.predict_proba(Xc)[:, 1])
    yc, gc = y[cal], groups[cal]
    ep_fam = episode_family(gc, meta["fam"].to_numpy()[cal])
    global_thr = float(pick_threshold_max_f1(scores, yc))  # finalize (:84)
    thr = pick_per_family_thresholds(scores, yc, ep_fam, fallback=global_thr)
    print(f"thresholds: global-maxF1={global_thr:.3f} "
          f"score-med-pos={float(np.median(scores[yc == 1])):.3f} "
          f"score-med-neg={float(np.median(scores[yc == 0])):.3f} "
          f"(n_pos={int(yc.sum())} n_neg={int((yc == 0).sum())}) (MEASURED)",
          flush=True)

    g05, g08 = 0.5, 0.8
    points = {"global-0.8 (locked)": g08, "global-0.5": g05, "per-family tuned": None}
    rep_eps = sorted(set(gc.tolist()))
    if args.max_eps:
        rep_eps = rep_eps[: args.max_eps]
    m = np.array([e in set(rep_eps) for e in gc])
    ym, gm = yc[m], gc[m]
    fault_eps = sorted({e for e in rep_eps if (ym[gm == e] == 1).any()})
    n_rep_windows = int(m.sum())
    for name, t in points.items():
        if t is None:
            dec = np.zeros(len(scores), dtype=int)
            for f in sorted(set(ep_fam.tolist())):
                mm = ep_fam == f
                dec[mm] = (scores[mm] >= thr[str(f)]).astype(int)
        else:
            dec = (scores >= t).astype(int)
        dm = dec[m]
        delays = stream_delays(dm, ym, gm, stride=STRIDE)
        fired_fault = {e for e in fault_eps if (dm[gm == e] == 1).any()}
        n_missed = len(fault_eps) - len(fired_fault)
        n_neg = sum(1 for d in delays if d < 0)
        print(
            f"stream-delay {name}: p50={float(np.median(delays)):.1f} "
            f"max={int(np.max(delays))} negfrac={n_neg/max(1,len(delays)):.2f} "
            f"n={len(delays)} fault-eps (missed={n_missed}/{len(fault_eps)}, "
            f"windows={n_rep_windows}, seed={args.seed}, "
            f"split=finalize-eps[2::3]) (MEASURED)",
            flush=True,
        )
    print(f"episodes: train={len(eps) - len(cal_eps)} heldout={len(cal_eps)} "
          f"reported={len(rep_eps)} (MEASURED)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
