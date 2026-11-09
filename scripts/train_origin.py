#!/usr/bin/env python3
"""Supervised origin head (Head-A v1): multiclass GBM over window features.

Labels are per-window roots (GT, train-only — detector stays clean).
Eval: episode top-1 by majority vote over predicted-fault windows,
plus held-machine transfer split (--cv machine).
"""

from __future__ import annotations

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd  # type: ignore[import-untyped]


def _oof_predict(
    X: np.ndarray,
    yr: np.ndarray,
    groups: np.ndarray,
    *,
    n_splits: int = 3,
    seed: int = 0,
    invariant: bool = False,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    from sklearn.ensemble import HistGradientBoostingClassifier  # type: ignore[import-untyped]
    from sklearn.model_selection import StratifiedGroupKFold  # type: ignore[import-untyped]

    from src.window_dataset import OBS_STRUCT_COLS, STRUCT_COLS, apply_norm, fit_clean_norm

    n_struct = len(STRUCT_COLS) if invariant else len(OBS_STRUCT_COLS)
    n_obs = 15 if invariant else X.shape[1] - 2 * n_struct
    classes = np.array(sorted(set(yr.tolist())))
    y = np.searchsorted(classes, np.asarray(yr))
    oof = np.zeros(len(X), dtype=int)
    proba = np.zeros((len(X), len(classes)))
    cv = StratifiedGroupKFold(n_splits=n_splits)
    splits = list(cv.split(X, y, groups))
    for tr, te in splits:
        med, iqr = fit_clean_norm(X[tr], (yr[tr] != "none").astype(int), n_obs)
        clf = HistGradientBoostingClassifier(max_iter=300, random_state=seed)
        clf.fit(apply_norm(X[tr], med, iqr, n_obs), y[tr])
        proba[te] = clf.predict_proba(apply_norm(X[te], med, iqr, n_obs))
        oof[te] = clf.predict(apply_norm(X[te], med, iqr, n_obs))
    return classes[oof], proba, classes


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="supervised origin-head OOF")
    ap.add_argument("--parquet", default="artifacts/m0b_mass_*.parquet")
    ap.add_argument("--w", type=int, default=128)
    ap.add_argument("--stride", type=int, default=8)
    ap.add_argument("--splits", type=int, default=3)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--build-jobs", type=int, default=1)
    ap.add_argument(
        "--identity",
        action="store_true",
        help="O2 ablation: per-channel (identity-carrying) features instead of invariant",
    )

    ap.add_argument(
        "--cv",
        default="episode",
        choices=("episode",),
        help="GroupKFold over episodes (in-fleet only: closed-set classifiers "
        "cannot name unseen machines; transfer needs open-set rankers)",
    )
    ap.add_argument("--save-oof", default="")
    args = ap.parse_args(argv)
    import glob as _glob

    from src.window_dataset import build_windows

    paths = sorted(_glob.glob(args.parquet))
    if not paths:
        raise SystemExit(f"no parquet shards match {args.parquet}")
    df = pd.concat([pd.read_parquet(p) for p in paths], ignore_index=True)
    out = build_windows(
        df,
        w=args.w,
        stride=args.stride,
        invariant=not args.identity,
        build_jobs=args.build_jobs,
        return_starts=True,
        return_roots=True,
    )
    X, y, fam, groups, _starts, roots = out
    pred, proba, oof_classes = _oof_predict(
        X, np.asarray(roots), np.asarray(groups), n_splits=args.splits, seed=args.seed,
        invariant=not args.identity,
    )
    hit_w = ((pred == np.asarray(roots)) & (np.asarray(y) == 1)).sum()
    tot_w = int((np.asarray(y) == 1).sum())
    print(
        f"window top1 (fault windows)={hit_w / max(1, tot_w):.3f} (MEASURED, n={tot_w})"
    )
    ep_hit, ep_n = 0, 0
    for ep in np.unique(groups):
        m = (groups == ep) & (pred != "none")
        if not m.any():
            continue
        truth = [
            str(x) for x in np.asarray(roots)[(groups == ep) & (np.asarray(y) == 1)]
        ]
        if not truth:
            continue
        vals, counts = np.unique(
            [str(x) for x in np.asarray(pred)[m]], return_counts=True
        )
        if vals[int(np.argmax(counts))] == max(set(truth), key=truth.count):
            ep_hit += 1
        ep_n += 1
    print(f"episode top1={ep_hit / max(1, ep_n):.3f} (MEASURED, n={ep_n})")
    if args.save_oof:
        frame = pd.DataFrame(
            {"pred": pred, "y": y, "fam": fam, "ep": groups, "root": np.asarray(roots)}
        )
        for i, c in enumerate(oof_classes):
            frame[f"proba_{c}"] = proba[:, i]
        frame.to_parquet(args.save_oof, index=False)
        print(f"oof saved -> {args.save_oof}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
