"""Calibration + fusion application tests (synthetic; real OOF in Task 17)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.apply_calibration import apply_calibration


def perfect_two_family_oof() -> pd.DataFrame:
    rows = []
    for fam in ("A", "B"):
        for i in range(20):
            rows.append({"family": fam, "y": 0, "s1": 0.0})
        for i in range(10):
            rows.append({"family": fam, "y": 1, "s1": 10.0})
    return pd.DataFrame(rows)


def test_perfect_scores_fuse_to_all_tp_no_fp():
    oof = perfect_two_family_oof()
    out = apply_calibration(
        oof, ["s1"], clean_mask=oof["y"] == 0, families=oof["family"]
    )
    assert out["fused"][out["y"] == 1].all() and not out["fused"][out["y"] == 0].any()
