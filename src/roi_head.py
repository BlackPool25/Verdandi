"""ROI point head: trigger-gated onset heatmap + origin-machine call (torch).

Trained on twin GT (origin tick/machine) — GT is train-only supervision,
never an inference input. Inference input: obs window around the detector
trigger. Kill-bars (owner 2026-11-09): leave-machines-out top-1 >= 0.50 and
onset err < 20 with no breakdown regression; ROI-permutation ablation must
remove the gain or the win is leakage.
"""

from __future__ import annotations

import numpy as np
import torch
from torch import nn


class RoiHead(nn.Module):
    """Causal 1D-CNN encoder + per-tick onset head + origin-machine head."""

    def __init__(self, n_chan: int, n_machine: int, width: int = 32) -> None:
        super().__init__()
        self.enc = nn.Sequential(
            nn.ConstantPad1d((4, 0), 0.0),
            nn.Conv1d(n_chan, width, 5),
            nn.ReLU(),
            nn.ConstantPad1d((4, 0), 0.0),
            nn.Conv1d(width, width, 5),
            nn.ReLU(),
            nn.ConstantPad1d((4, 0), 0.0),
            nn.Conv1d(width, width, 5),
            nn.ReLU(),
        )
        self.heat = nn.Conv1d(width, 1, 1)
        self.pool_q = nn.Conv1d(width, 1, 1)
        self.who = nn.Sequential(
            nn.Linear(width * 2, width), nn.ReLU(), nn.Linear(width, n_machine)
        )

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        f = self.enc(x)  # [B, W, T]
        heat = self.heat(f).squeeze(1)  # [B, T]
        w = torch.softmax(self.pool_q(f).squeeze(1), dim=1)  # [B, T]
        pooled = torch.cat([(f * w.unsqueeze(1)).sum(-1), f.amax(dim=-1)], dim=1)
        return heat, self.who(pooled)


def loss_fn(
    pred_heat: torch.Tensor,
    pred_who: torch.Tensor,
    heat: torch.Tensor,
    who: torch.Tensor,
    w_heat: float = 1.0,
) -> torch.Tensor:
    """BCE heatmap + CE origin call."""
    bce = nn.functional.binary_cross_entropy_with_logits(pred_heat, heat)
    ce = nn.functional.cross_entropy(pred_who, who)
    return w_heat * bce + ce


def gaussian_heat(t: int, pos: int, width: float = 5.0) -> np.ndarray:
    """1D Gaussian bump at pos (onset target)."""
    x = np.arange(t, dtype=float)
    return np.exp(-0.5 * ((x - pos) / width) ** 2).astype(float)


def episode_tensors(
    g,
    obs_cols: list[str],
    trigger: int,
    t0: int,
    machine_idx: int,
    back: int = 64,
    fwd: int = 192,
) -> tuple[np.ndarray, np.ndarray, int]:
    """Trigger-anchored input + targets. Prefix (0-30) z-scores the window.

    Returns (X[C,T] float32, heat[T] float32, who int). Raises ValueError
    if the ROI exceeds the episode bounds (caller skips such episodes).
    """
    import pandas as pd

    assert isinstance(g, pd.DataFrame)
    lo, hi = trigger - back, trigger + fwd
    if lo < 0 or hi > len(g):
        raise ValueError(f"ROI [{lo},{hi}) outside episode len {len(g)}")
    seg = g.iloc[lo:hi]
    pre = g.iloc[:30]
    out = []
    for c in obs_cols:
        v = seg[c].to_numpy(dtype=float)
        pv = pre[c].to_numpy(dtype=float)
        med = float(np.median(pv))
        mad = float(np.median(np.abs(pv - med)) * 1.4826) or 1e-9
        out.append(((v - med) / mad).astype(np.float32))
    X = np.stack(out, axis=0)
    heat = gaussian_heat(hi - lo, t0 - lo).astype(np.float32)
    return X, heat, int(machine_idx)
