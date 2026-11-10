"""Firing head + trailing buffer/flow features (cache-backed, low-RAM)."""

import numpy as np
import pandas as pd

CACHE = "artifacts/window_cache"


def main(cache: str | None = None):
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.model_selection import GroupKFold

    from src.window_dataset import apply_norm, fit_clean_norm

    CDIR = cache or CACHE
    try:
        X = np.load(f"{CDIR}/X_invariant.npy", mmap_mode="r")
        meta = pd.read_parquet(f"{CDIR}/meta.parquet")
        F = np.load(f"{CDIR}/F_flow.npy", mmap_mode="r")
    except FileNotFoundError:
        raise SystemExit("run scripts/cache_windows.py first (streams per shard)")
    y = meta["y"].to_numpy()
    groups = meta["ep"].to_numpy()
    starts = meta["start"].to_numpy()
    n_obs = 15
    for tag, Xall in (("obs-only", X), ("obs+flow", np.hstack([np.asarray(X), np.asarray(F)]))):
        med, iqr = fit_clean_norm(Xall, (y == 0).astype(int), n_obs)
        oof = np.zeros(len(Xall))
        cv = GroupKFold(n_splits=3)
        for tr, te in cv.split(Xall, y, groups):
            clf = HistGradientBoostingClassifier(max_iter=100, random_state=0)
            clf.fit(apply_norm(Xall[tr], med, iqr, n_obs), y[tr])
            oof[te] = clf.predict_proba(apply_norm(Xall[te], med, iqr, n_obs))[:, 1]
        fr = pd.DataFrame({"ep": groups, "start": starts, "p": oof, "y": y})
        truth = fr.groupby("ep")["y"].max()
        for thr in (0.5, 0.7):
            hits, n, cf, cn, errs = 0, 0, 0, 0, []
            for ep, g in fr.groupby("ep"):
                g = g.sort_values("start")
                hot = (g["p"].to_numpy() >= thr).astype(int)
                fired = any(
                    hot[max(0, i - 2) : i + 1].sum() >= 2 for i in range(len(hot))
                )
                if truth[ep] == 0:
                    cn += 1
                    cf += fired
                    continue
                n += 1
                if not fired:
                    continue
                hits += 1
                first = int(g["start"].iloc[int(np.flatnonzero(hot)[0])])
                errs.append(abs(first - int(g[g["y"] == 1]["start"].min())))
            errs = np.array(errs)
            print(f"{tag} thr={thr}: retrieval={hits/max(1,n):.3f} "
                  f"clean-fire={cf/max(1,cn):.3f} "
                  f"med-err={float(np.median(errs)) if len(errs) else -1:.1f} "
                  f"(MEASURED, n={n}/{cn})", flush=True)


if __name__ == "__main__":
    import argparse as _ap
    _p = _ap.ArgumentParser()
    _p.add_argument("--cache", default=None)
    _a = _p.parse_args()
    main(cache=_a.cache)
