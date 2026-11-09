#!/usr/bin/env python3
"""Finalize deployable window-GBM artifact (step 1 of ship).

Trains the base head on 2/3 of episodes, calibrates (sigmoid, prefit) on the
held-out third, picks per-family thresholds on calibrated calibration scores,
and saves model.joblib + thresholds.json + schema.json. No test data exists —
the calibration fold doubles as the honest validation slice (episodes the base
head never saw).
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import joblib
import numpy as np
import pandas as pd  # type: ignore[import-untyped]

from scripts.train_windows import episode_family, pick_per_family_thresholds
from src.train_pipeline import compute_raw_pointwise_f1, pick_threshold_max_f1
from src.window_dataset import OBS_STRUCT_COLS, STRUCT_COLS, apply_norm, build_windows, fit_clean_norm, struct_cols_for

STATS = ("mean", "std", "min", "max", "slope")


def feature_names(obs_cols: list[str], *, invariant: bool = False) -> list[str]:
    """Name each window feature in build_windows emission order."""
    if invariant:
        from src.window_dataset import INVARIANT_STATS

        names = [f"any.{s}.{k}" for k in STATS for s in INVARIANT_STATS]
    else:
        names = [f"{c}.{s}" for c in obs_cols for s in STATS]
    for c in struct_cols_for(invariant=invariant):
        if c == "stale_hold_run":
            names += [f"{c}.rate", f"{c}.max"]
        elif c == "cycle_lag":
            names += [f"{c}.max", f"{c}.mean"]
        else:
            names += [f"{c}.max", f"{c}.mean"]
    return names


def finalize(
    df: pd.DataFrame,
    *,
    out_dir: str,
    w: int = 32,
    stride: int = 8,
    seed: int = 0,
    battery_id: str = "m0b-mass-balanced-v1",
    invariant: bool = False,
    build_jobs: int = 1,
) -> dict:
    """Train, calibrate, threshold, save. Returns validation metrics + paths."""
    from sklearn.calibration import CalibratedClassifierCV  # type: ignore[import-untyped]
    from sklearn.ensemble import HistGradientBoostingClassifier  # type: ignore[import-untyped]

    obs_cols = [c for c in df.columns if c.startswith("obs_")]
    X, y, fam, groups = build_windows(
        df, w=w, stride=stride, invariant=invariant, build_jobs=build_jobs
    )
    eps = sorted(pd.unique(groups))
    cal_eps = set(eps[2::3])
    cal = np.array([e in cal_eps for e in groups])
    n_obs = 15 if invariant else X.shape[1] - 2 * len(OBS_STRUCT_COLS)
    norm_med, norm_iqr = fit_clean_norm(X[~cal], y[~cal], n_obs)
    Xn, Xc = (
        apply_norm(X[~cal], norm_med, norm_iqr, n_obs),
        apply_norm(X[cal], norm_med, norm_iqr, n_obs),
    )
    base = HistGradientBoostingClassifier(max_iter=300, random_state=seed)
    # Internal 3-fold cross-fit calibration on train episodes only; the held-out
    # calibration third stays unseen for threshold picking and validation.
    model = CalibratedClassifierCV(estimator=base, cv=3, method="sigmoid")
    model.fit(Xn, y[~cal])
    scores = np.asarray(model.predict_proba(Xc)[:, 1])
    ep_fam = episode_family(groups[cal], fam[cal])
    global_thr = float(pick_threshold_max_f1(scores, y[cal]))
    thr = pick_per_family_thresholds(scores, y[cal], ep_fam, fallback=global_thr)
    dec = np.zeros(len(scores), dtype=int)
    for f in sorted(set(ep_fam.tolist())):
        m = ep_fam == f
        dec[m] = (scores[m] >= thr[str(f)]).astype(int)
    f1 = compute_raw_pointwise_f1(y[cal], dec)
    out = pathlib.Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    names = feature_names(obs_cols, invariant=invariant)
    assert len(names) == X.shape[1], f"{len(names)} != {X.shape[1]}"
    joblib.dump(
        {
            "model": model,
            "thresholds": thr,
            "global_threshold": global_thr,
            "w": w,
            "stride": stride,
            "battery_id": battery_id,
            "invariant": bool(invariant),
            "norm_median": norm_med.tolist(),
            "norm_iqr": norm_iqr.tolist(),
            "n_obs_features": int(n_obs),
        },
        out / "model.joblib",
    )
    (out / "thresholds.json").write_text(json.dumps(thr, indent=2))
    (out / "schema.json").write_text(
        json.dumps(
            {
                "w": w,
                "stride": stride,
                "obs_cols": obs_cols,
                "struct_cols": list(struct_cols_for(invariant=bool(invariant))),
                "features": names,
                "battery_id": battery_id,
            },
            indent=2,
        )
    )
    return {
        "window_f1": float(f1),
        "n_windows": len(X),
        "n_features": int(X.shape[1]),
        "n_cal_episodes": len(cal_eps),
        "out_dir": str(out),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="finalize deployable window GBM")
    ap.add_argument("--parquet", default="artifacts/m0b_mass_*.parquet")
    ap.add_argument("--out", default="artifacts/window-gbm-v1")
    ap.add_argument("--w", type=int, default=32)
    ap.add_argument("--stride", type=int, default=8)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--invariant", action="store_true")
    ap.add_argument(
        "--build-jobs",
        type=int,
        default=1,
        help="worker processes for window building (episodes are independent)",
    )
    ap.add_argument("--battery-id", default="m0b-mass-balanced-v1")
    args = ap.parse_args(argv)
    import glob as _glob

    paths = sorted(_glob.glob(args.parquet))
    if not paths:
        raise SystemExit(f"no parquet shards match {args.parquet}")
    df = pd.concat([pd.read_parquet(p) for p in paths], ignore_index=True)
    r = finalize(
        df,
        out_dir=args.out,
        w=args.w,
        stride=args.stride,
        seed=args.seed,
        invariant=args.invariant,
        battery_id=args.battery_id,
        build_jobs=args.build_jobs,
    )
    print(
        f"finalized -> {r['out_dir']}: val window-F1={r['window_f1']:.4f} "
        f"({r['n_windows']} windows, {r['n_features']} feats, {r['n_cal_episodes']} cal eps)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
