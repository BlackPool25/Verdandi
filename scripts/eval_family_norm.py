#!/usr/bin/env python3
"""Norm-matched per-family comparison (W-normfam, Shreyas F21).

Claim under test: the recorded multiclass-vs-binary gap (multiclass window-F1
0.795 < binary 0.846, `docs/WINDOW_GBM_V1_MODEL_CARD.md:71-76`) is confounded
by normalization protocol — the multiclass head centers median/IQR on ALL
train rows (`scripts/train_multiclass.py:43-50`) while the binary head fits
clean-only (`scripts/train_windows.py:150`, `src/window_dataset.fit_clean_norm`).

This script re-runs BOTH heads under BOTH norms (2x2: {binary, multiclass} x
{clean, all}) on the same seed-pinned episode subsample, so the head effect is
measured with normalization matched. Analysis-only: writes no serving
artifacts (only `artifacts/eval_family_norm.json`, ignored analysis output).
Never touches `scripts/eval_stacked.py`.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import numpy as np


def fit_norm_all(X_tr: np.ndarray, n_obs: int) -> tuple[np.ndarray, np.ndarray]:
    """Median/IQR over ALL train rows (multiclass protocol)."""
    blk = np.asarray(X_tr, dtype=float)[:, :n_obs]
    med = np.median(blk, axis=0)
    iqr = np.maximum(
        np.quantile(blk, 0.75, axis=0) - np.quantile(blk, 0.25, axis=0), 1e-9
    )
    return np.asarray(med, dtype=float), np.asarray(iqr, dtype=float)


def fit_norm_clean(
    X_tr: np.ndarray, y_tr: np.ndarray, n_obs: int
) -> tuple[np.ndarray, np.ndarray]:
    """Median/IQR over clean train rows only (binary protocol)."""
    from src.window_dataset import fit_clean_norm

    return fit_clean_norm(np.asarray(X_tr, dtype=float),
                          np.asarray(y_tr, dtype=int), int(n_obs))


def _norm_for(protocol: str, X_tr: np.ndarray, y_tr: np.ndarray, n_obs: int):
    if protocol == "clean":
        return fit_norm_clean(X_tr, y_tr, n_obs)
    if protocol == "all":
        return fit_norm_all(X_tr, n_obs)
    raise ValueError(f"unknown norm protocol {protocol!r}")


def _gbm(seed: int, max_iter: int):
    from sklearn.ensemble import HistGradientBoostingClassifier

    return HistGradientBoostingClassifier(max_iter=max_iter, random_state=seed)


def run_matched_comparison(
    X: np.ndarray,
    y: np.ndarray,
    fam: np.ndarray,
    groups: np.ndarray,
    *,
    n_splits: int = 3,
    seed: int = 0,
    max_iter: int = 300,
    n_obs: int | None = None,
) -> dict[tuple[str, str], dict]:
    """2x2 OOF: {binary, multiclass} x {clean-norm, all-norm}.

    Same episodes throughout; each head keeps its own stratifier (binary
    stratifies on y, multiclass on fam) — what is matched is the
    normalization protocol within each column. n_obs leading columns are
    normalized (obs block; structural counters pass through untouched, the
    published protocol); None normalizes the full width. Returns per-cell
    {f1, n, per_family} with MEASURED lineage fields filled by main().
    """
    from sklearn.model_selection import StratifiedGroupKFold

    from src.train_pipeline import compute_raw_pointwise_f1
    from src.window_dataset import apply_norm

    X = np.asarray(X, dtype=float)
    y = np.asarray(y, dtype=int)
    fam = np.asarray(fam, dtype=object)
    groups = np.asarray(groups)
    n_obs = X.shape[1] if n_obs is None else int(n_obs)
    classes = np.array(sorted(set(fam.tolist())))
    y_multi = np.searchsorted(classes, fam)
    out: dict[tuple[str, str], dict] = {}
    for head in ("binary", "multiclass"):
        strat = y if head == "binary" else y_multi
        for protocol in ("clean", "all"):
            cv = StratifiedGroupKFold(n_splits=n_splits)
            oof_bin = np.zeros(len(X), dtype=int)
            oof_fam = np.array(["none"] * len(X), dtype=object)
            for tr, te in cv.split(X, strat, groups):
                med, iqr = _norm_for(protocol, X[tr], y[tr], n_obs)
                if head == "binary":
                    clf = _gbm(seed, max_iter)
                    clf.fit(apply_norm(X[tr], med, iqr, n_obs), y[tr])
                    oof_bin[te] = clf.predict(apply_norm(X[te], med, iqr, n_obs))
                else:
                    clf = _gbm(seed, max_iter)
                    clf.fit(apply_norm(X[tr], med, iqr, n_obs), y_multi[tr])
                    pred = classes[clf.predict(
                        apply_norm(X[te], med, iqr, n_obs))]
                    oof_fam[te] = pred
                    oof_bin[te] = (pred != "none").astype(int)
            per_family: dict[str, float] = {}
            for f in sorted(set(fam.tolist()) - {"none"}):
                if head == "binary":
                    m = (fam == f) & (y == 1)
                    per_family[str(f)] = round(float(oof_bin[m].mean())
                                               if m.sum() else 0.0, 4)
                else:
                    m = (fam == f) & (y == 1)
                    per_family[str(f)] = round(float((oof_fam[m] == f).mean())
                                               if m.sum() else 0.0, 4)
            out[(head, protocol)] = {
                "f1": round(float(compute_raw_pointwise_f1(y, oof_bin)), 4),
                "n": int(len(X)),
                "per_family": per_family,
            }
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="norm-matched family comparison")
    ap.add_argument("--parquet", default="artifacts/m0b_mass_c*.parquet")
    ap.add_argument("--episodes-per-family", type=int, default=24)
    ap.add_argument("--n-clean", type=int, default=72)
    ap.add_argument("--w", type=int, default=128)
    ap.add_argument("--stride", type=int, default=8)
    ap.add_argument("--splits", type=int, default=3)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--save", default="artifacts/eval_family_norm.json")
    args = ap.parse_args(argv)
    import glob as _glob

    import pandas as pd

    from src.window_dataset import build_windows

    paths = sorted(_glob.glob(args.parquet))
    if not paths:
        raise SystemExit(f"no parquet shards match {args.parquet}")
    rng = np.random.default_rng(args.seed)
    # Seed-pinned episode subsample: same episodes for all 4 cells.
    fam_of, clean_eps = {}, []
    for p in paths:
        cols = pd.read_parquet(p, columns=["episode_id", "fault_family"])
        for ep, g in cols.groupby("episode_id"):
            fams = set(g["fault_family"].tolist()) - {"none"}
            if fams:
                fam_of.setdefault(str(sorted(fams)[0]), set()).add(ep)
            else:
                clean_eps.append(ep)
    keep: set = set()
    fam_counts: dict[str, int] = {}
    for f, eps in sorted(fam_of.items()):
        pick = sorted(eps)[:0]  # placeholder replaced below (seed-pinned)
        idx = rng.choice(len(sorted(eps)), size=min(args.episodes_per_family,
                                                    len(eps)), replace=False)
        pick = [sorted(eps)[i] for i in idx]
        keep.update(pick)
        fam_counts[f] = len(pick)
    ci = rng.choice(len(clean_eps), size=min(args.n_clean, len(clean_eps)),
                    replace=False)
    keep.update(clean_eps[i] for i in ci)
    df = pd.concat([pd.read_parquet(p) for p in paths],
                   ignore_index=True)
    keep_df = pd.DataFrame({"episode_id": list(keep)})
    df = df.merge(keep_df, on="episode_id").reset_index(drop=True)
    X, y, fam, groups = build_windows(df, w=args.w, stride=args.stride,
                                      invariant=True)
    n_obs_note = "invariant-23: first 15 obs-stat cols normalized, 8 struct passthrough"
    res = run_matched_comparison(X, y, fam, groups, n_splits=args.splits,
                                 seed=args.seed, n_obs=15)
    payload = {
        "seed": args.seed,
        "parquet": args.parquet,
        "w": args.w,
        "stride": args.stride,
        "splits": args.splits,
        "n_windows": int(len(X)),
        "n_episodes": int(len(set(groups.tolist()))),
        "episode_ids": sorted(set(groups.tolist())),
        "episodes_per_family": fam_counts,
        "n_clean_episodes": int(len(ci)),
        "features": n_obs_note,
        "cells": {f"{h}/{p}": v for (h, p), v in res.items()},
    }
    for (h, p), v in res.items():
        print(f"{h:10s} norm={p:5s} window-F1={v['f1']:.4f} "
              f"(MEASURED, n={v['n']} windows, seed={args.seed})", flush=True)
        print(f"  per-family: {v['per_family']}", flush=True)
    b_c = res[("binary", "clean")]["f1"]
    m_c = res[("multiclass", "clean")]["f1"]
    b_a = res[("binary", "all")]["f1"]
    m_a = res[("multiclass", "all")]["f1"]
    print(f"matched-clean gap (multi-binary)={m_c - b_c:+.4f} "
          f"matched-all gap={m_a - b_a:+.4f} "
          f"published confounded gap={(m_a - b_c):+.4f} (multi/all vs bin/clean)",
          flush=True)
    if args.save:
        with open(args.save, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        print(f"saved {args.save}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
