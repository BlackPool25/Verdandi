"""CUSUM bank tests: fixed + adaptive-k, Bernoulli, EWMA, slope, spike path."""

import numpy as np


def test_tabular_cusum_fires_on_1sigma_shift():
    from src.cusum_bank import TabularCUSUM

    rng = np.random.default_rng(0)
    c = TabularCUSUM(k=0.5, h=5.0, mu0=0.0, sigma0=1.0)
    fired = [c.step(v) for v in rng.normal(0, 1, 20)] + [
        c.step(v) for v in rng.normal(1.0, 1, 60)
    ]
    assert any(fired[20:]) and not any(fired[:20])


def test_adaptive_cusum_tracks_variance_shift():
    from src.cusum_bank import TabularCUSUM

    rng = np.random.default_rng(2)
    c = TabularCUSUM(k=0.5, h=5.0, mu0=0.0, sigma0=1.0, adaptive=True)
    quiet = [c.step(v) for v in rng.normal(0, 0.5, 40)]
    assert not any(quiet)
    loud_shift = [c.step(v) for v in rng.normal(1.5, 1.5, 80)]
    assert any(loud_shift)


def test_baseline_frozen_across_second_fit():
    from src.cusum_bank import TabularCUSUM

    c = TabularCUSUM(k=0.5, h=5.0, mu0=0.0, sigma0=1.0)
    c.fit([10.0] * 50)
    assert (c.mu0, c.sigma0) == (0.0, 1.0)


def test_bernoulli_cusum_reference_from_clean_only():
    from src.cusum_bank import BernoulliCUSUM

    rng = np.random.default_rng(1)
    clean = (rng.random(2000) < 0.005).astype(int)
    c = BernoulliCUSUM.fit_rate(clean, h=3.0)
    assert 0.003 < c.r < 0.010
    hot = (rng.random(500) < 0.03).astype(int)
    assert any(c.step(int(v)) for v in hot)


def test_spike_absorbed_by_cusum_but_caught_by_fast_path():
    from src.cusum_bank import SpikePath, TabularCUSUM

    c = TabularCUSUM(k=0.5, h=5.0, mu0=0.0, sigma0=1.0)
    s = SpikePath(w=4, thr=3.0)
    xs = np.zeros(50)
    xs[25] = 3.5
    assert not any(c.step(v) for v in xs)
    assert any(s.step(v) for v in xs)


def _planted(kind: str, n: int = 300, t0: int = 150, seed: int = 0):
    rng = np.random.default_rng(seed)
    base = rng.normal(0, 1, n)
    if kind == "ramp":
        base[t0:] += np.linspace(0, 3, n - t0)
    elif kind == "level":
        base[t0:] += 2.0
    elif kind == "spike":
        base[t0 + 5] += 4.0
    return base


def test_family_heads_fire_on_own_signature():
    from src.cusum_bank import EWMA, SlopePersist, SpikePath, TabularCUSUM

    ramp, level, spike = (
        _planted("ramp"),
        _planted("level"),
        _planted("spike"),
    )
    # drift head: EWMA + slope persistence on ramp
    e, sp = EWMA(lam=0.2, mu0=0.0, limit=1.0), SlopePersist(w=64, need=10)
    drift_fires = [e.step(v)[1] or sp.step(v) for v in ramp]
    assert any(drift_fires[150:])
    # bias head: tabular CUSUM on level
    c = TabularCUSUM(k=0.5, h=5.0, mu0=0.0, sigma0=1.0)
    assert any(c.step(v) for v in level[150:])
    # spike head: fast path on transient, drift ramps stay quiet-ish
    s = SpikePath(w=4, thr=3.0)
    assert any(s.step(v) for v in spike)
    s2 = SpikePath(w=4, thr=3.0)
    ramp_fires = sum(s2.step(v) for v in ramp[:200])
    assert ramp_fires / 200 < 0.05  # white-noise first-diffs trip ~3%/tick: quantified, not zero
