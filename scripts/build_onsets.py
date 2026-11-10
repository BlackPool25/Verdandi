"""Per-episode per-machine onsets (diagnose_multi_origin over battery). Cached."""

import numpy as np
import pandas as pd


def build_onsets(df: pd.DataFrame, obs_cols: list[str]):
    from src.diagnose import diagnose_multi_origin
    from src.twin import _DOWNSTREAM_MACHINES

    edges = {k: list(v) for k, v in _DOWNSTREAM_MACHINES.items()}
    rows = []
    for ep, g in df.groupby("episode_id", sort=False):
        g = g.sort_values("step").reset_index(drop=True)
        try:
            entries = diagnose_multi_origin(g, obs_cols)
        except Exception:
            continue
        for r in entries:
            rows.append({
                "ep": ep, "machine": r["machine"], "onset": r["onset"],
                "onset_kind": r["onset_kind"], "own_state": r["own_state"],
            })
    return pd.DataFrame(rows, columns=["ep", "machine", "onset", "onset_kind", "own_state"])


if __name__ == "__main__":
    import glob
    import sys

    sys.path.insert(0, ".")
    paths = sorted(glob.glob("artifacts/m0b_mass_*.parquet"))
    df = pd.concat([pd.read_parquet(p) for p in paths], ignore_index=True)
    obs = [c for c in df.columns if c.startswith("obs_")]
    out = build_onsets(df, obs)
    out.to_parquet("artifacts/onsets.parquet", index=False)
    print(f"saved artifacts/onsets.parquet rows={len(out)}", flush=True)
