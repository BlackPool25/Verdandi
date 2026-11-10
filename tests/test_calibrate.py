"""Task 1: calibration module (TDD RED)."""

import numpy as np


def _overconfident_logits(n=200, k=4, seed=0):
    rng = np.random.default_rng(seed)
    y = rng.integers(0, k, size=n)
    pred = (y + (rng.uniform(0, 1, n) < 0.3).astype(int)) % k  # 30% wrong
    logits = rng.normal(0, 0.2, (n, k))
    logits[np.arange(n), pred] += 4.0  # confident, sometimes wrong
    return logits, y


def test_temperature_reduces_nll():
    from src.calibrate import fit_temperature, nll

    logits, y = _overconfident_logits()
    base = nll(logits, 1.0, y)
    T = fit_temperature(logits, y)
    assert T > 1.0
    assert nll(logits, T, y) < base


def test_ece_known_value():
    from src.calibrate import ece_score

    # 20 samples: hand-computed 15-bin top-label ECE checked inline below.
    probs = np.array([[0.9, 0.1]] * 10 + [[0.6, 0.4]] * 10)
    y = np.array([0] * 8 + [1] * 2 + [0] * 6 + [1] * 4)
    # bin high: conf 0.9, acc 0.8 -> |0.1|*10/20=0.05; bin mid: conf 0.6, acc 0.6 -> 0
    assert abs(ece_score(probs, y, n_bins=15) - 0.05) < 1e-9


def test_platt_monotone_and_bounded():
    from src.calibrate import platt_fit, platt_predict

    rng = np.random.default_rng(0)
    margins = np.concatenate([rng.normal(-1, 1, 100), rng.normal(1, 1, 100)])
    correct = np.array([0] * 100 + [1] * 100)
    a, b = platt_fit(margins, correct)
    p = platt_predict(margins, a, b)
    assert p.min() > 0.0 and p.max() < 1.0
    assert bool(np.all(np.diff(p[np.argsort(margins)]) >= 0))


def test_coverage_curve_tradeoff():
    from src.calibrate import coverage_curve

    conf = np.array([0.9, 0.8, 0.7, 0.2, 0.1])
    correct = np.array([1, 1, 1, 0, 0])
    pts = coverage_curve(conf, correct)
    assert len(pts) == 5 and pts[0][0] == 1.0
    assert abs(pts[0][1] - 0.4) < 1e-12  # 2/5 wrong at full coverage
    assert abs(pts[2][1] - 0.0) < 1e-12  # top-3 all right
    risks = [r for _, r in pts]
    assert min(risks) <= risks[0]  # selection can only help here


def test_pick_threshold_hits_risk_target():
    from src.calibrate import coverage_curve, pick_threshold

    rng = np.random.default_rng(2)
    conf = rng.uniform(0, 1, 400)
    correct = (rng.uniform(0, 1, 400) < conf).astype(int)
    tau = pick_threshold(conf, correct, risk_target=0.2)
    m = conf >= tau
    assert m.mean() > 0.1 and (1 - correct[m].mean()) <= 0.2 + 1e-9
    pts = coverage_curve(conf, correct)
    assert any(abs(c - m.mean()) < 1e-9 for c, _ in pts)
