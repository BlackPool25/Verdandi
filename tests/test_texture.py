"""Texture DR tests: AR/sine/eps knobs, defaults golden-compatible."""

import pytest


def test_default_texture_matches_unoverridden():
    from src import twin

    a = twin.run_episode(777, None)
    b = twin.run_episode(777, None, texture={"ar_coef": 0.6, "sine_amp": 0.5, "eps_scale": 0.5})
    assert a["obs"] == b["obs"]


def test_texture_knobs_change_obs_but_keep_shape():
    from src import twin

    base = twin.run_episode(777, None)
    dr = twin.run_episode(777, None, texture={"ar_coef": 0.2, "sine_amp": 1.0, "eps_scale": 0.5})
    assert dr["T"] == base["T"]
    assert dr["obs"] != base["obs"]
    # determinism under override
    again = twin.run_episode(777, None, texture={"ar_coef": 0.2, "sine_amp": 1.0, "eps_scale": 0.5})
    assert dr["obs"] == again["obs"]


def test_texture_rejects_bad_ranges():
    from src import twin

    with pytest.raises(ValueError):
        twin.run_episode(777, None, texture={"ar_coef": 1.5, "sine_amp": 0.5, "eps_scale": 0.5})
    with pytest.raises(ValueError):
        twin.run_episode(777, None, texture={"ar_coef": 0.6, "sine_amp": -1.0, "eps_scale": 0.5})
