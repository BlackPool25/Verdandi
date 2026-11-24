"""Task 2 RED: eval_stacked.main must materialize ranker-calibration input.

Stage2 OOF npz is the ranker-level fit input (T+Platt need per-episode
scores + labels + groups + family for stratified clean-val/OOF splits).
"""
import pathlib

import numpy as np

REQUIRED_KEYS = {"oof_pred", "y", "groups", "fam"}


def test_stage2_oof_npz_present_with_ranker_fit_keys():
    p = pathlib.Path("artifacts/stage2-oof.npz")
    assert p.exists(), "eval_stacked.main must save artifacts/stage2-oof.npz"
    z = np.load(str(p), allow_pickle=True)
    missing = REQUIRED_KEYS - set(z.files)
    assert not missing, f"npz missing ranker-fit keys: {missing}"
    n = len(z["y"])
    assert len(z["oof_pred"]) == n and len(z["groups"]) == n and len(z["fam"]) == n
    assert n > 0
