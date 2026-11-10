"""Hybrid vs teacher-rows on the focused ON arm (Task 4 measurement)."""
import glob

import numpy as np
import pandas as pd


def main():
    import scripts.eval_stacked as es
    from scripts.build_onsets import build_onsets
    from src.twin import _MACHINE_ORDER

    machines = list(_MACHINE_ORDER)
    oof = pd.read_parquet("artifacts/focused_on_oof.parquet")
    obese = sorted(glob.glob("artifacts/v2_focus/on/shard_*.parquet"))
    df = pd.concat([pd.read_parquet(p) for p in obese], ignore_index=True)
    obs = [c for c in df.columns if c.startswith("obs_")]
    ons = build_onsets(df, obs)
    fm = es.flowmap_from_cache("artifacts/cache_v2_on",
                               "artifacts/v2_focus/on/shard_*.parquet", machines)
    base = es.build_rows(oof, machines, None, ons)
    hyb = es.build_rows_hybrid(oof, machines, None, ons, fm)
    vot = set(ep for ep, g in oof.groupby("ep") if (g["pred"] != "none").any())
    for tag, (X, y, groups, fam) in (("teacher-rows", base), ("hybrid", hyb)):
        p = es._run_lambdarank(X, y, groups, fam)
        hits = n = vh = vn = 0
        for ep in np.unique(groups):
            m = groups == ep
            hit = int(np.argsort(-p[m])[0] == int(np.argmax(y[m])))
            hits += hit
            n += 1
            if ep in vot:
                vh += hit
                vn += 1
        print(f"{tag}: pooled={hits/max(1,n):.3f} (n={n}) "
              f"votable={vh/max(1,vn):.3f} (n={vn}) (MEASURED)", flush=True)


if __name__ == "__main__":
    main()
