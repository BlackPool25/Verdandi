"""Path-level eval: is the true propagation route in the top-k paths?"""

import glob

import numpy as np
import pandas as pd


def main(n_eps: int = 200, k: int = 3, seed: int = 0):
    from src.diagnose import diagnose_multi_origin
    from src.possibility import kbest_paths
    from src.route import extract_route
    from src.twin import _DOWNSTREAM_MACHINES

    edges = {kk: list(vv) for kk, vv in _DOWNSTREAM_MACHINES.items()}
    paths = sorted(glob.glob("artifacts/m0b_mass_*.parquet"))
    df = pd.concat([pd.read_parquet(p) for p in paths], ignore_index=True)
    rng = np.random.default_rng(seed)
    eps = rng.choice(sorted(df["episode_id"].unique()), size=n_eps, replace=False)
    obs_cols = [c for c in df.columns if c.startswith("obs_")]
    state_cols = {c[6:] for c in df.columns if c.startswith("state_")}

    def is_subseq(path, route):
        it = iter(route)
        return all(any(m == r for r in it) for m in path)

    root_hit, subseq_hit, nk, n = 0, 0, [], 0
    for ep in eps:
        g = df[df["episode_id"] == ep].sort_values("step").reset_index(drop=True)
        truth = g[g["root_id"] != "none"]
        if truth.empty:
            continue
        root = str(truth["root_id"].mode().iloc[0])
        route = extract_route(g, root, edges)
        if len(route) < 1:
            continue
        n += 1
        entries = diagnose_multi_origin(g, obs_cols)
        if not entries:
            continue
        changed = {r["machine"] for r in entries}
        anchor = max(entries, key=lambda r: r["onset"])["machine"]
        from src.possibility import neighborhood

        nb = neighborhood(anchor, changed, edges, radius=2)
        ev = {}
        for r in entries:
            if r["machine"] not in nb:
                continue
            s = 1.0 if (r["onset_kind"] == "state" and r["own_state"] == "DOWN") else 0.5 if r["onset_kind"] in ("state", "counter") else 0.2
            ev[r["machine"]] = {"onset": r["onset"], "score": s}
        if anchor not in ev:
            continue
        paths = kbest_paths(ev, edges, anchor, k=k)
        nk.append(len(paths))
        if paths and paths[0][0][0] == root:
            root_hit += 1
        if any(is_subseq(p, route) for p, _ in paths):
            subseq_hit += 1
    print(f"episodes={n} root-hit@1={root_hit/max(1,n):.3f} "
          f"route-subseq@{k}={subseq_hit/max(1,n):.3f} "
          f"mean-k={float(np.mean(nk)) if nk else 0:.1f} (MEASURED)")


if __name__ == "__main__":
    main()
