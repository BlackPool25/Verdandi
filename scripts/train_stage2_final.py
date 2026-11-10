"""Train final stage-2 ranker on all episodes (serving artifact)."""

import numpy as np
import pandas as pd

import sys

sys.path.insert(0, ".")


def main():
    from scripts.eval_stacked import build_rows, load_onsets
    from src.stage2 import save, train_final
    from src.twin import _MACHINE_ORDER

    oof = pd.read_parquet("artifacts/oof_identity.parquet")
    machines = list(_MACHINE_ORDER)
    try:
        frz = pd.read_parquet("artifacts/frozen_oof.parquet")
        foof = oof.sort_values(["ep"])
        ffrz = frz.sort_values(["ep", "start"])
        if (foof.groupby("ep").size() == ffrz.groupby("ep").size()).all():
            fired = pd.Series((ffrz["p"].to_numpy() >= 0.6), index=foof.index)
        else:
            fired = None
    except FileNotFoundError:
        fired = None
    X, y, groups, _ = build_rows(oof, machines, fired, load_onsets())
    model = train_final(X, y, groups)
    save(model, "artifacts/stage2-rank.txt")
    print(f"saved artifacts/stage2-rank.txt rows={len(y)}", flush=True)


if __name__ == "__main__":
    main()
