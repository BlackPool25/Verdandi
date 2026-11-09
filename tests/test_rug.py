"""Sensor-rug tests (deterministic, identity-off, audit sanity)."""

from __future__ import annotations

import numpy as np


def test_rug_identity_when_no_spec_and_deterministic_on_seed():
    from src.rug import apply_sensor_rug

    rng = np.random.default_rng(0)
    x = rng.normal(10, 1, size=(50, 4))
    assert np.array_equal(apply_sensor_rug(x, np.ones(4)), x)
    a = apply_sensor_rug(
        x,
        np.ones(4),
        rng=np.random.default_rng(1),
        spec={
            "floor_mult": (1.0, 2.0),
            "drift_abs": 0.05,
            "gain": (0.95, 1.05),
            "dropout_rate": 0.05,
            "clip_sigma": 8.0,
        },
    )
    b = apply_sensor_rug(
        x,
        np.ones(4),
        rng=np.random.default_rng(1),
        spec={
            "floor_mult": (1.0, 2.0),
            "drift_abs": 0.05,
            "gain": (0.95, 1.05),
            "dropout_rate": 0.05,
            "clip_sigma": 8.0,
        },
    )
    assert np.array_equal(a, b) and not np.array_equal(a, x)


def test_dropout_holds_last_value_and_floor_table_flags_uniformity():
    from src.rug import apply_sensor_rug, noise_floor_table

    x = np.ones((20, 2))
    out = apply_sensor_rug(
        x,
        np.ones(2),
        rng=np.random.default_rng(0),
        spec={"floor_mult": (1.0, 1.0), "dropout_rate": 1.0, "clip_sigma": 8.0},
    )
    assert np.all(out == 1.0)  # hold-first on constant signal stays constant
    floors = noise_floor_table(
        np.random.default_rng(2).normal(0, [1.0, 5.0], size=(500, 2))
    )
    assert abs(floors[0] - 1.0) < 0.2 and abs(floors[1] - 5.0) < 0.5


def test_discriminator_chance_on_identical_shifted_on_shift():
    from src.rug import twin_discriminator_auc

    rng = np.random.default_rng(3)
    a = rng.normal(0, 1, size=(120, 6))
    b = rng.normal(0, 1, size=(120, 6))
    assert 0.4 < twin_discriminator_auc(a, b, seed=0) < 0.6
    c = rng.normal(2, 1, size=(120, 6))
    assert twin_discriminator_auc(a, c, seed=0) > 0.9
