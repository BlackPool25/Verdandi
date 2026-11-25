"""Norm-matched per-family comparison tests (W-normfam, Shreyas F21).

RED-first: these import scripts.eval_family_norm, which does not exist yet.
All synthetic + tiny (no battery); determinism pinned by seed.
"""

from __future__ import annotations

import numpy as np


def _blobs(seed: int = 0):
    rng = np.random.default_rng(seed)
    parts, fams, groups, ys = [], [], [], []
    for i, fam in enumerate(["a", "b", "none"]):
        for ep in range(6):
            n = 30
            parts.append(rng.normal(i * 6.0, 1.0, size=(n, 6)))
            fams += [fam] * n
            ys += [0 if fam == "none" else 1] * n
            groups += [i * 100 + ep] * n
    return (np.vstack(parts), np.array(ys, dtype=int),
            np.array(fams, dtype=object), np.array(groups))


def test_norm_protocols_differ_on_contaminated_data():
    from scripts.eval_family_norm import fit_norm_all, fit_norm_clean

    X, y, _, _ = _blobs()
    med_c, _ = fit_norm_clean(X, y, n_obs=6)
    med_a, _ = fit_norm_all(X, n_obs=6)
    # clean-only centers on the clean blob (~12); all-row median is pulled away
    assert abs(float(np.mean(med_c)) - 12.0) < 1.0
    assert abs(float(np.mean(med_a)) - float(np.mean(med_c))) > 1.0


def test_clean_norm_ignores_fault_rows_all_norm_does_not():
    from scripts.eval_family_norm import fit_norm_all, fit_norm_clean

    X, y, _, _ = _blobs()
    X2 = X.copy()
    X2[y == 1] += 100.0  # move fault rows only
    mc1, _ = fit_norm_clean(X, y, n_obs=6)
    mc2, _ = fit_norm_clean(X2, y, n_obs=6)
    ma1, _ = fit_norm_all(X, n_obs=6)
    ma2, _ = fit_norm_all(X2, n_obs=6)
    np.testing.assert_allclose(mc1, mc2, rtol=1e-9)
    assert float(np.abs(ma2 - ma1).max()) > 1.0


def test_matched_comparison_returns_four_norm_matched_cells():
    from scripts.eval_family_norm import run_matched_comparison

    X, y, fam, groups = _blobs()
    res = run_matched_comparison(X, y, fam, groups, n_splits=2,
                                 seed=0, max_iter=10)
    assert set(res) == {("binary", "clean"), ("binary", "all"),
                        ("multiclass", "clean"), ("multiclass", "all")}
    for cell in res.values():
        assert 0.0 <= cell["f1"] <= 1.0
        assert cell["n"] == len(y)
        assert set(cell["per_family"]) >= {"a", "b"}
    # separable blobs: both heads under matched norms score high
    assert res[("binary", "clean")]["f1"] > 0.90
    assert res[("multiclass", "clean")]["f1"] > 0.90


def test_matched_comparison_is_seed_deterministic():
    from scripts.eval_family_norm import run_matched_comparison

    X, y, fam, groups = _blobs()
    r1 = run_matched_comparison(X, y, fam, groups, n_splits=2,
                                seed=0, max_iter=10)
    r2 = run_matched_comparison(X, y, fam, groups, n_splits=2,
                                seed=0, max_iter=10)
    for k in r1:
        assert r1[k]["f1"] == r2[k]["f1"]
        assert r1[k]["per_family"] == r2[k]["per_family"]


def test_n_obs_passthrough_matches_full_width_on_trees():
    from scripts.eval_family_norm import run_matched_comparison

    X, y, fam, groups = _blobs()
    # HistGBM trees are invariant to per-column affine rescaling, so
    # normalizing only the obs block (n_obs=4) must match full-width norms.
    r_full = run_matched_comparison(X, y, fam, groups, n_splits=2,
                                    seed=0, max_iter=10)
    r_part = run_matched_comparison(X, y, fam, groups, n_splits=2,
                                    seed=0, max_iter=10, n_obs=4)
    for k in r_full:
        assert r_part[k]["f1"] == r_full[k]["f1"]
