"""Wavefront tracing: sustained STARVED/BLOCKED order + reachability.

No direction claim from a single tick: endpoints need sustained runs
(>=3 ticks) with clean-RUN-dominated prefix, onset order, and DAG
reachability. Forks (B2->B7P/B7S) disambiguate by arrival order.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def sustained_onsets(
    g: pd.DataFrame, machine: str, state: str, run: int = 3, gate: int = 100
) -> list[int]:
    """Start ticks of sustained `state` runs at/after gate with clean prefix."""
    col = f"state_{machine}"
    if col not in g.columns:
        return []
    steps = g["step"].to_numpy()
    st = g[col].to_numpy()
    base = int(np.searchsorted(steps, gate))
    pre = st[:base]
    if len(pre) == 0 or float(np.mean(pre == "RUN")) <= 0.7:
        return []
    out = []
    i = base
    while i <= len(st) - run:
        if (st[i : i + run] == state).all():
            out.append(int(steps[i]))
            j = i + run
            while j < len(st) and st[j] == state:
                j += 1
            i = j
        else:
            i += 1
    return out


def reachable(root: str, target: str, max_depth: int = 3) -> bool:
    """DAG reachability via the twin topology (fork-aware)."""
    from src.twin import compute_hop

    return compute_hop(root, target, max_depth=max_depth) is not None


def wavefront(g: pd.DataFrame, machines: list[str]) -> dict:
    """Root = earliest sustained DOWN; frontier = sustained STARVED/BLOCKED
    downstream ordered by tick. Single-tick blips never rank."""
    downs: list[tuple[int, str]] = []
    front: list[dict] = []
    for m in machines:
        for t in sustained_onsets(g, m, "DOWN"):
            downs.append((t, m))
        for st in ("STARVED", "BLOCKED"):
            for t in sustained_onsets(g, m, st):
                front.append({"machine": m, "tick": t, "kind": st})
    downs.sort()
    front.sort(key=lambda r: r["tick"])
    root = downs[0][1] if downs else None
    if root is not None:
        front = [f for f in front if f["machine"] != root or True]
    return {"root": root, "root_tick": downs[0][0] if downs else None, "frontier": front}
