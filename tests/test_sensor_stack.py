"""Task 4: sensor stack (D-PCA -> RBC-T2/PDC-Q -> EBF), TDD RED."""

import numpy as np


def _syn(n_clean=500, n_fault=100, p=6, jfault=2, mag=8.0, seed=0):
    # Large amplitude: paper shows isolation needs fault >> modeling error.
    # Smearing at small mag is the documented effect, not a code bug.
    rng = np.random.default_rng(seed)
    A = rng.normal(0, 1, (p, 2))
    Zc = rng.normal(0, 1, (n_clean, 2))
    Zf = rng.normal(0, 1, (n_fault, 2))
    Xc = Zc @ A.T + rng.normal(0, 0.1, (n_clean, p))
    Xf = Zf @ A.T + rng.normal(0, 0.1, (n_fault, p))
    Xf[:, jfault] += mag
    return Xc, Xf, jfault


def test_dpca_augment_shape():
    from src.sensor_stack import dpca_augment

    X = np.zeros((50, 6))
    Z = dpca_augment(X, d=10)
    assert Z.shape == (40, 66)  # (T-d, n*(d+1)) causal rows, cf. paper Z in R^{m x nd}
    assert np.array_equal(Z, dpca_augment(X, d=10))


def test_rbc_t2_isolates_faulty_sensor():
    from src.sensor_stack import dpca_augment, fit_pca, rbc_t2

    Xc, Xf, j = _syn()
    Zc, Zf = dpca_augment(Xc, d=2), dpca_augment(Xf, d=2)
    P, lam, mu, sd = fit_pca(Zc, var_keep=0.98)
    C = rbc_t2(Zf, P, lam, mu, sd)
    base = C.reshape(len(C), -1, 6).sum(axis=1)  # fold lags -> base vars
    # Majority-right, not perfect: smearing to correlated vars is the
    # documented effect (paper: guarantees hold only for large amplitudes).
    assert float((base.argmax(axis=1) == j).mean()) > 0.7


def test_pdc_q_challenger_runs():
    from src.sensor_stack import dpca_augment, fit_pca, pdc_q

    Xc, Xf, j = _syn()
    Zc, Zf = dpca_augment(Xc, d=2), dpca_augment(Xf, d=2)
    P, lam, mu, sd = fit_pca(Zc, var_keep=0.98)
    C = pdc_q(Zf, P, mu, sd)
    assert C.shape == Zf.shape
    base = C.reshape(len(C), -1, 6).sum(axis=1)
    assert float((base.argmax(axis=1) == j).mean()) > 0.5


def test_ebf_paper_params():
    # Cartocci (25)(26): +0.01 winner / -0.005 rest, clip [0,1], thr 0.2.
    from src.sensor_stack import ebf_filter

    n, p, j = 300, 4, 1
    rng = np.random.default_rng(7)
    idx = rng.integers(0, p, n)  # scattered: no clear winner pre-fault
    idx[100:] = j  # persistent fault from k=100
    idx[200::17] = 2  # intermittent false argmax during fault
    alarm = ebf_filter(idx, n_vars=p, up=0.01, down=0.005, thr=0.2)
    assert alarm[99] == False  # type: ignore
    assert alarm[150:].mean() > 0.9  # dominates after transient (~20 steps)
    assert alarm[:100].mean() < 0.3  # scattered pre-fault stays below thr
