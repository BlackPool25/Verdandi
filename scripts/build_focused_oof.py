"""Focused-arm teacher OOF + onsets (Task 4 input builder)."""
import numpy as np
import pandas as pd


def build_focused_oof(cache: str, out_path: str):
    from scripts.train_origin import _oof_predict

    X = np.load(f"{cache}/X_identity.npy")
    meta = pd.read_parquet(f"{cache}/meta.parquet")
    yr = meta["root"].to_numpy(dtype=str)
    groups = meta["ep"].to_numpy()
    pred, proba, classes = _oof_predict(X, yr, groups)
    out = pd.DataFrame({"ep": groups, "pred": pred, "y": (yr != "none").astype(int),
                        "root": yr, "fam": meta["fam"].to_numpy(dtype=str),
                        "start": meta["start"].to_numpy()})
    for i, c in enumerate(classes):
        if c != "none":
            out[f"proba_{c}"] = proba[:, i]
    out.to_parquet(out_path, index=False)
    print(f"saved {out_path} rows={len(out)}", flush=True)


if __name__ == "__main__":
    import sys
    build_focused_oof(sys.argv[1], sys.argv[2])
