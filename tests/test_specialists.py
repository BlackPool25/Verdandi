"""Task 3: per-family specialists (TDD RED)."""

import numpy as np


def test_mask_stable_across_seeds():
    from src.specialists import select_mask

    rng = np.random.default_rng(0)
    Xc = rng.normal(0, 1, (500, 10))
    Xc[:, 3] *= 0.2  # low-variance channel
    m1 = select_mask(Xc, k=4, seed=0)
    m2 = select_mask(Xc, k=4, seed=1)
    assert len(m1) == 4 and set(m1) == set(m2)


def test_ewma_quiet_on_clean():
    from src.specialists import ewma_head

    rng = np.random.default_rng(0)
    x = rng.normal(0, 1, 300)
    hits = ewma_head(x, lam=0.3, k=3.0)
    assert hits.sum() / len(x) <= 0.01  # bounded FAR on clean (ARL-tuned h)


def test_cusum_detects_ramp_fast():
    from src.specialists import cusum_head

    rng = np.random.default_rng(0)
    x = np.concatenate([rng.normal(0, 1, 100), np.linspace(0, 3, 60)])
    det = cusum_head(x, k=0.5, h=5.0)
    assert det is not None and det < 160  # caught within the ramp


def test_expert_recall_on_synthetic_shift():
    from src.specialists import expert_score, fit_family_mask

    rng = np.random.default_rng(3)
    # 10 channels, families shift channel 2 by +3.5 in fault windows
    Xc = rng.normal(0, 1, (400, 10))
    Xf = rng.normal(0, 1, (100, 10)); Xf[:, 2] += 3.5
    mask = fit_family_mask(Xc, Xf, k=2)
    assert 2 in mask
    sc = expert_score(Xc, mask, Xc.mean(0), Xc.std(0))
    sf = expert_score(Xf, mask, Xc.mean(0), Xc.std(0))
    thr = float(np.quantile(sc, 0.95))
    assert float((sf > thr).mean()) > 0.8  # recall @5% FAR for this SNR


def test_trajectory_cusum_catches_ramp_misses_flat():
    from src.specialists import trajectory_score, tune_h

    rng = np.random.default_rng(4)
    clean = [rng.normal(0, 1, 22) for _ in range(200)]
    h = tune_h(clean, far=0.05)
    ramp = np.concatenate([rng.normal(0, 1, 10), np.linspace(0, 2.5, 12)])
    assert trajectory_score(ramp, h=h) == 1
    fa = np.mean([trajectory_score(t, h=h) for t in clean])
    assert fa <= 0.05


def test_lagged_stats_shape_and_determinism():
    from src.specialists import lagged_stats

    rng = np.random.default_rng(5)
    seq = rng.normal(0, 1, (40, 6))  # 40 windows, 6 channels
    L1 = lagged_stats(seq, d=10)
    L2 = lagged_stats(seq, d=10)
    assert L1.shape == (40, 6 * 2)  # lag-mean + lag-max per channel
    assert np.array_equal(L1, L2)


def test_cusum_on_lagged_ramp_recall():
    from src.specialists import cusum_head, lagged_stats, tune_h

    rng = np.random.default_rng(6)
    clean = []
    for _ in range(60):
        L = lagged_stats(rng.normal(0, 1, (22, 4)), d=5)
        clean.append((L[:, 0] - L[:, 0].mean()) / (L[:, 0].std() + 1e-9))
    h = tune_h(clean, far=0.05)
    ramp_seq = np.concatenate([rng.normal(0, 1, (8, 4)),
                               rng.normal(0, 1, (16, 4)) + np.linspace(0, 2.5, 16)[:, None]])
    Lr = lagged_stats(ramp_seq, d=5)
    traj = (Lr[:, 0] - Lr[:, 0].mean()) / (Lr[:, 0].std() + 1e-9)
    assert cusum_head(traj, k=0.5, h=h) is not None  # ramp detected
    fa = np.mean([cusum_head(t, k=0.5, h=h) is not None for t in clean])
    assert fa <= 0.05
