"""Probe: family classification + prune recall on frozen battery (TDD-style script)."""

import glob

import numpy as np
import pandas as pd


def main():
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.model_selection import StratifiedGroupKFold

    from src.window_dataset import OBS_STRUCT_COLS, apply_norm, build_windows, fit_clean_norm

    paths = sorted(glob.glob("artifacts/m0b_mass_*.parquet"))
    df = pd.concat([pd.read_parquet(p) for p in paths], ignore_index=True)
    out = build_windows(
        df, w=128, stride=8, invariant=True, build_jobs=4,
        return_starts=True, return_roots=True,
    )
    X, y, fam, groups, starts, roots = out
    fam = np.asarray(fam)
    n_obs = 15  # invariant=True hardcoded above

    # 1. family classification on fault windows only
    m = (np.asarray(y) == 1) & (fam != "none")
    Xf, yf, gf = X[m], fam[m], np.asarray(groups)[m]
    classes = np.array(sorted(set(yf.tolist())))
    yi = np.searchsorted(classes, yf)
    oof = np.zeros(len(yf), dtype=int)
    cv = StratifiedGroupKFold(n_splits=3)
    y_all = np.asarray(y)
    for tr, te in cv.split(Xf, yi, gf):
        med, iqr = fit_clean_norm(X, y_all, n_obs)  # clean rows of full battery
        clf = HistGradientBoostingClassifier(max_iter=300, random_state=0)
        clf.fit(apply_norm(Xf[tr], med, iqr, n_obs), yi[tr])
        oof[te] = clf.predict(apply_norm(Xf[te], med, iqr, n_obs))
    pred = classes[oof]
    acc = float((pred == yf).mean())
    print(f"family window-acc={acc:.3f} (MEASURED, n={len(yf)})")
    for c in classes:
        mc = yf == c
        print(f"  {c}: acc={float((pred[mc]==c).mean()):.3f} n={int(mc.sum())}")

    # 2. prune recall: radius-2 both-dirs closure around changed set contains root
    from src.possibility import neighborhood
    from src.twin import _DOWNSTREAM_MACHINES, _UPSTREAM_MACHINES

    fwd = {k: list(v) for k, v in _DOWNSTREAM_MACHINES.items()}
    edges = {k: sorted(set(fwd.get(k, []))) for k in set(fwd) | set(_UPSTREAM_MACHINES)}
    # per-episode: changed = machines with fault windows; trigger = earliest onset machine
    roots_arr = np.asarray(roots)
    ep_hit, ep_n, sizes = 0, 0, []
    for ep in np.unique(groups):
        me = (np.asarray(groups) == ep) & (np.asarray(y) == 1)
        if not me.any():
            continue
        truth = [str(x) for x in roots_arr[me]]
        truth = [t for t in truth if t != "none"]
        if not truth:
            continue
        root = max(set(truth), key=truth.count)
        # changed set: distinct predicted-fault machines unknown pre-diagnosis;
        # proxy: machines owning fault windows (oracle changed set -> upper bound)
        changed = set(str(x) for x in roots_arr[me] if str(x) != "none")
        nb = neighborhood(root, changed, edges, radius=2)
        sizes.append(len(nb))
        if root in nb:
            ep_hit += 1
        ep_n += 1
    print(f"prune recall (oracle changed, radius-2)={ep_hit/max(1,ep_n):.3f} n={ep_n} "
          f"mean_set={float(np.mean(sizes)):.1f} (MEASURED)")


if __name__ == "__main__":
    main()
