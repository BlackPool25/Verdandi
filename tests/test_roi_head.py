"""ROI head tests: shapes + synthetic overfit (torch lives in src/roi_head only)."""

import numpy as np


def _batch():
    rng = np.random.default_rng(0)
    X = rng.normal(0, 1, size=(4, 8, 120)).astype(np.float32)
    X[:, 3, 60:] += 4.0  # channel 3 steps at tick 60
    heat = np.zeros((4, 120), dtype=np.float32)
    heat[:, 60] = 1.0
    who = np.full((4,), 3, dtype=np.int64)
    return X, heat, who


def test_forward_shapes():
    import torch

    from src.roi_head import RoiHead

    m = RoiHead(n_chan=8, n_machine=8)
    X, _, _ = _batch()
    heat, who = m(torch.from_numpy(X))
    assert heat.shape == (4, 120) and who.shape == (4, 8)


def test_overfit_step_reduces_loss():
    import torch

    from src.roi_head import RoiHead, loss_fn

    torch.manual_seed(0)
    m = RoiHead(n_chan=8, n_machine=8)
    opt = torch.optim.Adam(m.parameters(), lr=1e-2)
    Xb, hb, wb = _batch()
    X, h, w = torch.from_numpy(Xb), torch.from_numpy(hb), torch.from_numpy(wb)
    l0 = loss_fn(m(X)[0], m(X)[1], h, w).item()
    for _ in range(30):
        opt.zero_grad()
        ph, pw = m(X)
        loss_fn(ph, pw, h, w).backward()
        opt.step()
    ph, pw = m(X)
    l1 = loss_fn(ph, pw, h, w).item()
    assert l1 < l0 * 0.5, (l0, l1)


def test_episode_tensors_trigger_anchored():
    import pandas as pd

    from src.roi_head import episode_tensors

    n = 300
    rng = np.random.default_rng(0)
    g = pd.DataFrame(
        {
            "step": list(range(n)),
            **{f"obs_M{i}": rng.normal(0, 1, size=n) for i in range(4)},
        }
    )
    X, heat, who = episode_tensors(
        g, [f"obs_M{i}" for i in range(4)], trigger=150, t0=160, machine_idx=2, fwd=100
    )
    assert X.shape == (4, 164) and heat.shape == (164,) and who == 2
    assert int(np.argmax(heat)) == 160 - (150 - 64)
    try:
        episode_tensors(
            g, [f"obs_M{i}" for i in range(4)], trigger=10, t0=160, machine_idx=2
        )
        raise AssertionError("expected ValueError")
    except ValueError:
        pass
