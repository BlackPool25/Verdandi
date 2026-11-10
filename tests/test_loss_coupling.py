"""Task 3: DEGRADE-flagged parts roll sink rejects (loss count-coupling, TDD)."""

import copy

import pytest


def _loss_ep():
    return {"class": "loss", "origin": "C7", "t0": 150, "dur": 35,
            "mag_sigma": 0.5, "extra": {"drop_rate": 0.5}}


def test_degrade_parts_roll_sink_rejects():
    from src import twin

    base = {"class": "loss", "origin": "B2", "t0": 150, "dur": 35,
            "mag_sigma": 0.5, "extra": {"drop_rate": 0.3}}
    hits = 0
    for seed in range(11, 19):
        rec = twin.run_episode(seed, dict(base))
        if sum(1 for e in rec["events"] if e.get("event") == "REJECT_ROUTE") > 0:
            hits += 1
    assert hits >= 1  # unmeasured loss parts condemned at sink (some seeds)


def test_clean_episode_no_sink_rejects():
    from src import twin

    for seed in range(11, 19):
        rec = twin.run_episode(seed, None)
        n = sum(1 for e in rec["events"] if e.get("event") == "REJECT_ROUTE")
        assert n == 0


def test_no_amplitude_change_from_coupling():
    # Gains frozen: same seed => identical obs amplitudes (drops only
    # stale-hold prior values, coupling adds no signal energy).
    import numpy as np

    from src import twin

    rec = twin.run_episode(11, _loss_ep())
    clean = twin.run_episode(11, None)
    assert np.abs(np.asarray(rec["obs"])).max() == \
        np.abs(np.asarray(clean["obs"])).max()
