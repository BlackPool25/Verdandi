"""Simplified range-based VUS-PR (threshold-free primary metric).

For buffer length l: dilate label segments by l, compute point-wise
precision/recall of thresholded scores against dilated labels, PR-AUC over a
score-quantile threshold grid. VUS-PR = mean AUC over the buffer grid.
Clean episodes (no positives) yield NaN and are excluded from averages.
"""

from __future__ import annotations

import numpy as np


def dilate(labels: np.ndarray, buffer: int) -> np.ndarray:
    """Binary dilation: mark ticks within `buffer` of any positive tick."""
    y = np.asarray(labels, dtype=bool)
    if buffer <= 0 or not y.any():
        return y
    idx = np.flatnonzero(y)
    lo = max(0, idx.min() - buffer)
    hi = min(y.size, idx.max() + buffer + 1)
    out = np.zeros_like(y)
    out[lo:hi] = True
    # Dilation must not bridge across separate far-apart segments: rebuild per segment.
    out[:] = False
    for s, e in _segments(y):
        out[max(0, s - buffer) : min(y.size, e + buffer)] = True
    return out


def _segments(mask: np.ndarray) -> list[tuple[int, int]]:
    y = np.asarray(mask, dtype=bool)
    edges = np.diff(y.astype(int))
    starts: list[int] = [int(v) + 1 for v in np.flatnonzero(edges == 1)]
    ends: list[int] = [int(v) + 1 for v in np.flatnonzero(edges == -1)]
    if y[0]:
        starts = [0] + starts
    if y[-1]:
        ends = ends + [y.size]
    return list(zip(starts, ends))


def range_pr_auc(
    scores: np.ndarray, labels: np.ndarray, *, buffer: int = 0, n_thresholds: int = 50
) -> float:
    """PR-AUC of score-thresholded alarms vs buffer-dilated labels."""
    s = np.asarray(scores, dtype=float).ravel()
    y = np.asarray(labels, dtype=int).ravel()
    if s.size != y.size or not y.any():
        return float("nan")
    lab = dilate(y, buffer)
    denom_lab = lab.sum()
    if denom_lab == 0:
        return float("nan")
    lo, hi = float(s.min()), float(s.max())
    grid = np.unique(np.quantile(s, np.linspace(0, 1, n_thresholds)))
    if grid.size < 2 or hi == lo:
        return float("nan")
    recalls, precisions = [0.0], [1.0]
    for t in sorted(grid, reverse=True):
        pred = s >= t
        tp = float(np.logical_and(pred, lab).sum())
        n_pred = float(pred.sum())
        recalls.append(tp / denom_lab)
        precisions.append(tp / n_pred if n_pred else 1.0)
    recalls.append(1.0)
    precisions.append(0.0)
    order = np.argsort(recalls, kind="stable")
    r = np.asarray(recalls)[order]
    p = np.asarray(precisions)[order]
    best = np.maximum.accumulate(p[::-1])[::-1]
    # Step-function (average-precision) integration: trapezoid overestimates
    # single-point alarms (it credits the empty span between operating points).
    dr = np.diff(r, prepend=0.0)
    return float(np.sum(dr * best))


def vus_pr(
    scores: np.ndarray, labels: np.ndarray, *, buffers: tuple = (0, 5, 10, 20)
) -> float:
    """Mean range-PR-AUC over buffer lengths (NaN-aware)."""
    aucs = [range_pr_auc(scores, labels, buffer=b) for b in buffers]
    return float(np.nanmean(aucs)) if any(np.isfinite(aucs)) else float("nan")
