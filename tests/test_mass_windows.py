"""Mass battery + window GBM smoke tests (tiny; full run is scripts/* main)."""

from __future__ import annotations

import numpy as np


def test_mass_specs_balanced_and_deterministic():
    from scripts.gen_mass_battery import build_specs

    fe, ce, faults = build_specs(n_per_cell=2, n_clean=4, seed=0)
    assert len(fe) == 7 * 2 * 2 and len(ce) == 4
    fe2, _, _ = build_specs(n_per_cell=2, n_clean=4, seed=0)
    assert fe == fe2
    fams = [faults[ep]["class"] for ep in set(fe)]
    assert {fams.count(f) for f in set(fams)} == {4}
    assert not (set(fe) & set(ce)), "fault/clean episode IDs must be disjoint"
    origins = {faults[ep]["origin"] for ep in fe}
    assert len(origins) > 1, "faults must span machines, not a single origin"
    t0s = {faults[ep]["t0"] for ep in fe}
    assert len(t0s) > 1, "fault onset must vary across episodes"


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


def test_per_family_thresholds_beat_global_on_shifted_families():
    from scripts.train_windows import pick_per_family_thresholds

    rng = np.random.default_rng(0)
    s = np.concatenate(
        [
            rng.normal(0, 1, 50),
            rng.normal(2, 1, 10),
            rng.normal(5, 1, 50),
            rng.normal(7, 1, 10),
        ]
    )
    y = np.array([0] * 50 + [1] * 10 + [0] * 50 + [1] * 10)
    fam = np.array(["a"] * 60 + ["b"] * 60)
    thr = pick_per_family_thresholds(s, y, fam)
    assert set(thr) == {"a", "b"} and thr["b"] > thr["a"]
    from src.train_pipeline import compute_raw_pointwise_f1

    dec = np.zeros_like(y)
    for f in ("a", "b"):
        dec[fam == f] = (s[fam == f] >= thr[f]).astype(int)
    glob = (s >= np.median(s)).astype(int)
    assert compute_raw_pointwise_f1(y, dec) >= compute_raw_pointwise_f1(y, glob)


def test_degenerate_all_negative_slice_falls_back_to_global():
    from scripts.train_windows import pick_per_family_thresholds

    s = np.array([0.1, 0.2, 0.8, 0.9])
    y = np.array([0, 0, 0, 0])
    fam = np.array(["none"] * 4)
    thr = pick_per_family_thresholds(s, y, fam, fallback=0.5)
    assert thr["none"] == 0.5


def test_episode_family_labels_clean_windows_with_episode_family():
    from scripts.train_windows import episode_family

    ef = episode_family(
        np.array([1, 1, 1, 2, 2, 2]),
        np.array(["none", "delay", "none", "none", "none", "none"]),
    )
    assert ef.tolist() == ["delay"] * 3 + ["none"] * 3


def test_save_oof_writes_scored_windows(tmp_path):
    import pandas as pd

    from scripts.gen_mass_battery import main as gen_main
    from scripts.train_windows import main

    assert (
        gen_main(
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
                "8",
            ]
        )
        == 0
    )
    out = tmp_path / "oof.parquet"
    rc = main(
        [
            "--parquet",
            str(tmp_path / "mass_*.parquet"),
            "--splits",
            "2",
            "--save-oof",
            str(out),
        ]
    )
    assert rc == 0
    df = pd.read_parquet(out)
    assert {"score", "dec", "y", "fam", "ep"} <= set(df.columns) and len(df) > 0


def test_parallel_folds_match_serial_oof(tmp_path):
    import pandas as pd

    from scripts.gen_mass_battery import main as gen_main
    from scripts.train_windows import main

    assert (
        gen_main(
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
                "32",
            ]
        )
        == 0
    )
    outs = []
    for j in ("1", "2"):
        out = tmp_path / f"oof{j}.parquet"
        rc = main(
            [
                "--parquet",
                str(tmp_path / "mass_*.parquet"),
                "--splits",
                "2",
                "--save-oof",
                str(out),
                "--n-jobs",
                j,
                "--invariant",
            ]
        )
        assert rc == 0
        outs.append(pd.read_parquet(out))
    assert np.array_equal(outs[0]["score"].to_numpy(), outs[1]["score"].to_numpy())


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
