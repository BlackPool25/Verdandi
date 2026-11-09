"""Twin-fork cascade forecast: fault-branch vs clean-branch diff.

Separate re-simulation (no GT peeking): inputs are prefix + diagnosed
fault only. Sim == truth today, so the API boundary is the discipline.
"""

from __future__ import annotations


def predict_cascade(
    seed: int, fault: dict, t_det: int, h: int = 150
) -> list[tuple[str, int, int]]:
    """Return [(machine, first_hit_tick, hop_est)] over [t_det, t_det+h].

    Affected = non-RUN state in fault-branch but RUN in clean-branch.
    Root itself included when it deviates. Ordered by hit tick.
    """
    from src.twin import _MACHINE_ORDER, compute_hop, run_episode

    f_rec = run_episode(seed, dict(fault))
    c_rec = run_episode(seed, None)
    order = list(_MACHINE_ORDER)
    n = len(f_rec["states"][0])
    lo, hi = max(0, t_det), min(n, t_det + h)
    out: list[tuple[str, int, int]] = []
    root = fault.get("origin")
    for i, name in enumerate(order):
        fs, cs = f_rec["states"][i], c_rec["states"][i]
        hit = -1
        for t in range(lo, hi):
            if fs[t] != "RUN" and cs[t] == "RUN":
                hit = t
                break
        if hit >= 0:
            hop = compute_hop(root, name, max_depth=3)
            out.append((name, hit, -1 if hop is None else hop))
    out.sort(key=lambda r: r[1])
    return out
