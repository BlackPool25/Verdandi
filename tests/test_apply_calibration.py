"""Calibration + fusion application tests (synthetic; real OOF in Task 17)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.apply_calibration import apply_calibration


def perfect_two_family_oof() -> pd.DataFrame:
    rows = []
    for ep, fam in ((1, "A"), (2, "A"), (3, "B"), (4, "B")):
        for i in range(20):
            rows.append({"episode_id": ep, "family": fam, "y": 0, "s1": 0.0})
        for i in range(10):
            rows.append({"episode_id": ep, "family": fam, "y": 1, "s1": 10.0})
    return pd.DataFrame(rows)


def test_perfect_scores_fuse_to_all_tp_no_fp():
    oof = perfect_two_family_oof()
    out = apply_calibration(
        oof, ["s1"], clean_mask=oof["y"] == 0, families=oof["family"]
    )
    assert out["fused"][out["y"] == 1].all() and not out["fused"][out["y"] == 0].any()


def test_uninformative_family_abstains_instead_of_flag_all():
    rng = np.random.default_rng(0)
    n = 60
    oof = pd.DataFrame(
        {
            "episode_id": [1] * 30 + [2] * 30,
            "family": ["U"] * n,
            "y": [0] * 58 + [1] * 2,
            "s1": rng.normal(0, 1, size=n),
        }
    )
    out = apply_calibration(
        oof, ["s1"], clean_mask=oof["y"] == 0, families=oof["family"]
    )
    assert not out["fused"].any()


def window_veto_oof():
    import pandas as pd

    rows = []
    for i in range(10):
        rows.append(
            {
                "episode_id": 1,
                "fid": "F-06",
                "family": "spike",
                "y": 1 if i < 2 else 0,
                "s1": 10.0,
                "in_window": i < 2,
            }
        )
    return pd.DataFrame(rows)


def test_veto_fires_only_inside_window():
    oof = window_veto_oof()
    out = apply_calibration(
        oof,
        ["s1"],
        clean_mask=oof["y"] == 0,
        families=oof["family"],
        ids=oof["fid"],
        window_mask=oof["in_window"],
    )
    assert out["fused"][oof["in_window"]].all() and not out["fused"][~oof["in_window"]].any()


def shifted_episode_oof():
    import numpy as np
    import pandas as pd

    # One family, two episodes: B's clean sits 8 sigma below A's, and B's faults
    # (+5 sigma locally) hide inside A's clean bulk globally. Only per-episode
    # normalization separates them without flagging A's clean steps.
    rng = np.random.default_rng(0)
    rows = []
    spec = [(1, 0.0, 0), (2, -8.0, 10)]
    for ep, shift, n_fault in spec:
        n = 100
        s = rng.normal(shift, 1.0, size=n)
        y = np.zeros(n, dtype=int)
        s[:n_fault] = shift + 5.0
        y[:n_fault] = 1
        for i in range(n):
            rows.append(
                {
                    "episode_id": ep,
                    "fid": "F-X",
                    "family": "spike",
                    "y": int(y[i]),
                    "s1": float(s[i]),
                }
            )
    return pd.DataFrame(rows)


def test_episode_normalization_centers_clean():
    oof = shifted_episode_oof()
    out = apply_calibration(
        oof, ["s1"], clean_mask=oof["y"] == 0, families=oof["family"]
    )
    assert out["fused"][oof["y"] == 1].all() and out["fused"][oof["y"] == 0].sum() <= 2


def test_recall_floor_beats_maxf1_recall_on_weak_family():
    import numpy as np

    from src.apply_calibration import pick_recall_floor_thresholds

    rng = np.random.default_rng(0)
    s = np.concatenate([rng.normal(0, 1, 90), rng.normal(1.0, 1, 10)])
    y = np.array([0] * 90 + [1] * 10)
    thr = pick_recall_floor_thresholds(s, y, np.array(["w"] * 100), floor=0.7)["w"]
    r = ((s >= thr).astype(int) & y).sum() / y.sum()
    assert r >= 0.7
