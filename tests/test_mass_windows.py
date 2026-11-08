"""Mass battery + window GBM smoke tests (tiny; full run is scripts/* main)."""

from __future__ import annotations

import numpy as np


def test_mass_specs_balanced_and_deterministic():
    from scripts.gen_mass_battery import build_specs

    fe, ce, faults = build_specs(n_per_cell=2, n_clean=4, seed=0)
    assert len(fe) == 7 * 2 * 2 and len(ce) == 4
    fe2, _, _ = build_specs(n_per_cell=2, n_clean=4, seed=0)
    assert fe == fe2
    fams = [faults[ep]["class"] for ep in fe]
    assert {fams.count(f) for f in set(fams)} == {4}


def test_all_clean_shard_exports(tmp_path):
    from scripts.gen_mass_battery import main

    rc = main(
        [
            "--n-per-cell",
            "1",
            "--n-clean",
            "2",
            "--seed",
            "0",
            "--manifest",
            str(tmp_path / "m.json"),
            "--out",
            str(tmp_path / "mass.parquet"),
            "--shard-eps",
            "2",
        ]
    )
    assert rc == 0
    assert (tmp_path / "m.json").exists()


def test_binary_gbm_separates_windows_and_episode_hit():
    from scripts.train_windows import episode_hit_rate, train_binary_gbm

    rng = np.random.default_rng(0)
    X = np.vstack([rng.normal(0, 1, (40, 8)), rng.normal(4, 1, (40, 8))])
    y = np.array([0] * 40 + [1] * 40)
    clf = train_binary_gbm(X, y)
    pred = clf.predict(X)  # type: ignore[union-attr]
    assert (pred == y).mean() > 0.90
    ep = episode_hit_rate(
        np.array([0, 0, 1, 1, 0]),
        np.array([1, 1, 2, 2, 3]),
        np.array(["none", "none", "delay", "delay", "none"]),
    )
    assert ep["hit_rate"] == 1.0 and ep["clean_fp_rate"] == 0.0
