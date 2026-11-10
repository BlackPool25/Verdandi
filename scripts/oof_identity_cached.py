"""Identity OOF from window cache (no rebuild). Persists to artifacts/."""

import numpy as np
import pandas as pd

CACHE = "artifacts/window_cache"
OUT = "artifacts/oof_identity.parquet"


def main():
    import sys

    sys.path.insert(0, ".")
    from scripts.train_origin import _oof_predict

    X = np.load(f"{CACHE}/X_identity.npy", mmap_mode="r")
    meta = pd.read_parquet(f"{CACHE}/meta.parquet")
    roots = meta["root"].to_numpy(dtype=str)
    groups = meta["ep"].to_numpy()
    pred, proba, classes = _oof_predict(
        np.asarray(X), roots, groups, n_splits=3, seed=0, invariant=False,
    )
    frame = pd.DataFrame({
        "pred": pred, "y": meta["y"].to_numpy(), "fam": meta["fam"].to_numpy(),
        "ep": groups, "root": roots,
    })
    for i, c in enumerate(classes):
        frame[f"proba_{c}"] = proba[:, i]
    frame.to_parquet(OUT, index=False)
    print(f"saved {OUT} rows={len(frame)}", flush=True)


if __name__ == "__main__":
    main()
