"""Diagnosis layer tests (alongside detector, silent on clean)."""

import numpy as np
import pandas as pd


def _seg(n=40, shift=None):
    rng = np.random.default_rng(0)
    base = rng.normal(0, 1, size=(n, 2))
    if shift:
        ch, amt = shift
        base[:, ch] += amt
    return pd.DataFrame({"obs_A0": base[:, 0], "obs_A1": base[:, 1]})


def test_attribution_picks_shifted_channel():
    from src.diagnose import attribute_machine, episode_nominal, robust_sigma

    g = _seg()
    nom = episode_nominal(g, ["obs_A0", "obs_A1"])
    sig = robust_sigma(g, ["obs_A0", "obs_A1"])
    seg = _seg(shift=(1, 8.0))
    m, s = attribute_machine(seg, ["obs_A0", "obs_A1"], nom, sig)
    assert m == "A1" and s > 3.0


def test_coordination_single_vs_multi():
    from src.diagnose import classify_coordination, episode_nominal, robust_sigma

    g = _seg()
    cols = ["obs_A0", "obs_A1"]
    nom, sig = episode_nominal(g, cols), robust_sigma(g, cols)
    assert classify_coordination(_seg(shift=(0, 8.0)), cols, nom, sig) == "sensor"
    both = _seg()
    both.iloc[-1, 0] += 8.0
    both.iloc[-1, 1] += 8.0
    assert classify_coordination(both, cols, nom, sig) == "process"


def test_rung_cut():
    from src.diagnose import estimate_rung

    assert estimate_rung(2.0) == "incipient" and estimate_rung(5.0) == "caricature"


def test_diagnose_window_shape():
    from src.diagnose import diagnose_window, episode_nominal, robust_sigma

    g = _seg()
    cols = ["obs_A0", "obs_A1"]
    out = diagnose_window(
        _seg(shift=(0, 8.0)), cols, episode_nominal(g, cols), robust_sigma(g, cols)
    )
    assert set(out) == {"machine", "score_sigma", "coord_class", "rung", "hop_est"}
    assert out["hop_est"] == 0
