"""Gate-61 obs-only regression: calibration gate inputs must be obs-driven.

stale_hold_run / reject_flag_count (and down_run) are GT-anchored counter
scores (v6 root-anchored branch with zero fallback; clean rows constant) and
must NEVER feed temperature scaling + Platt (fit or serve) nor the margin
they validate on. This test poisons those columns and requires byte-identical
gate outputs; any future leak fails loudly here.
"""

import numpy as np
import pandas as pd

from src.window_dataset import (
    GT_ANCHORED_COLS,
    OBS_STRUCT_COLS,
    build_windows,
)

BANNED = ("stale_hold_run", "reject_flag_count", "down_run")
EDGES = {"A0": ["B9"], "B9": []}
COLS = ["obs_A0", "obs_B9"]
STUB = {"T": 2.58, "a": 5.0, "b": -3.0, "tau": 0.739, "risk_target": 0.3}


def _incident_df(seed=0, a0_onset=185, b9_onset=195, n=300):
    rng = np.random.default_rng(seed)
    fault = np.array([0] * a0_onset + [1] * (n - a0_onset))
    return pd.DataFrame(
        {
            "episode_id": [1] * n,
            "step": list(range(n)),
            "y": fault,
            "fault_family": ["none"] * a0_onset + ["breakdown"] * (n - a0_onset),
            "root_id_step": ["none"] * a0_onset + ["A0"] * (n - a0_onset),
            "obs_A0": np.concatenate(
                [rng.normal(0, 1, a0_onset), rng.normal(0, 1, n - a0_onset) + 6.0]
            ),
            "obs_B9": np.concatenate(
                [rng.normal(0, 1, b9_onset), rng.normal(0, 1, n - b9_onset) + 6.0]
            ),
            "state_A0": ["RUN"] * a0_onset + ["DOWN"] * (n - a0_onset),
            "state_B9": ["RUN"] * n,
            "cycle_lag": [0] * n,
            "degrade_flag_count": [0] * n,
        }
    )


def _poisoned(g, val=999.0):
    g2 = g.copy()
    for c in BANNED:
        g2[c] = val
    return g2


def test_obs_struct_cols_exclude_gt_anchored():
    assert not (set(OBS_STRUCT_COLS) & set(GT_ANCHORED_COLS)), (
        f"GT-anchored leak in identity struct cols: "
        f"{set(OBS_STRUCT_COLS) & set(GT_ANCHORED_COLS)}"
    )
    for c in BANNED:
        assert c not in OBS_STRUCT_COLS


def test_window_features_immune_to_banned_poison():
    g = _incident_df()
    gp = _poisoned(g)
    kw = dict(w=32, stride=8, invariant=False)
    (X,) = (build_windows(g, **kw)[0],)
    (Xp,) = (build_windows(gp, **kw)[0],)
    assert X.shape == Xp.shape
    np.testing.assert_array_equal(X, Xp)
    # Width proves only the clean two struct cols are featurized:
    # 5 stats x 2 obs + 2 stats x len(OBS_STRUCT_COLS).
    assert X.shape[1] == 5 * 2 + 2 * len(OBS_STRUCT_COLS)


def test_gate_conf_immune_to_banned_poison():
    from src.diagnose import diagnose_incident

    outs = []
    for frame in (_incident_df(), _poisoned(_incident_df())):
        rep = diagnose_incident(
            frame, COLS, 190, EDGES, calibrator=dict(STUB, tau=float("-inf"))
        )
        outs.append(rep)
    a, b = outs
    assert a["root"] == b["root"]
    assert a["confidence"]["top1"] == b["confidence"]["top1"]
    assert a.get("abstain") == b.get("abstain")


def test_gate_abstain_immune_to_banned_poison():
    from src.diagnose import diagnose_incident

    outs = []
    for frame in (_incident_df(), _poisoned(_incident_df())):
        rep = diagnose_incident(frame, COLS, 190, EDGES, calibrator=dict(STUB))
        outs.append(rep)
    assert outs[0].get("abstain") == outs[1].get("abstain")
    assert outs[0]["root"] == outs[1]["root"]


def test_fit_script_reads_only_teacher_probas():
    import pathlib

    src = pathlib.Path("scripts/fit_calibration.py").read_text(encoding="utf-8")
    for c in BANNED:
        assert c not in src, f"fit script references GT-anchored {c}"
    assert "proba_" in src
    diag = pathlib.Path("src/diagnose.py").read_text(encoding="utf-8")
    gate_section = diag[diag.index("Calibration gate"):]
    for c in BANNED:
        assert c not in gate_section, f"gate section references {c}"
