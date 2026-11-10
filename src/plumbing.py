"""Plumbing audit: does each fault's effect reach a monitored variable?

Paired fault-on/off sims at fixed seed; per-carrier max |z| vs the
fault-off baseline. Carriers are live-computable channels only —
nothing GT-anchored (see GT_ANCHORED_COLS) and no label prefixes.
"""

from __future__ import annotations

import numpy as np

CARRIERS: dict[str, list[str]] = {
    "breakdown": ["obs", "current", "state"],
    "drift": ["obs", "current", "state"],
    "bias": ["obs", "current", "state"],
    "spike": ["obs", "current", "state"],
    # count deficit must move flow/buffer counters or downstream arrivals
    "loss": ["obs", "current", "state", "buffer", "flow"],
    # rejects must move the test-sink / flow counters, not just origin obs
    "quality": ["obs", "current", "state", "buffer", "flow"],
}


def _series(rec: dict, kind: str, key: str) -> np.ndarray | None:
    from src.twin import _MACHINE_ORDER

    order = list(_MACHINE_ORDER)
    if kind in ("obs", "current", "state"):
        arr = rec.get({"obs": "obs", "current": "currents", "state": "states"}[kind])
        if arr is None or key not in order:
            return None
        v = np.asarray(arr[order.index(key)])
        return v if kind == "state" else v.astype(float)
    if kind == "buffer":
        bufs = rec.get("buffers")
        if bufs is None:
            return None
        try:
            return np.asarray(bufs[int(key)], dtype=float)
        except (ValueError, IndexError):
            return None
    if kind == "flow":
        if key == "throughput":
            tp = rec.get("throughput")
            return np.asarray(tp, dtype=float).ravel() if tp is not None else None
        fs = rec.get("flow_stats", {})
        v = fs.get(key)
        return np.array([float(v)]) if v is not None else None
    return None


def _carrier_keys(rec: dict, origin: str, carriers: list[str]) -> list[tuple[str, str]]:
    from src.twin import _MACHINE_ORDER

    keys: list[tuple[str, str]] = []
    if "obs" in carriers:
        keys.append(("obs", origin))
    if "current" in carriers:
        keys.append(("current", origin))
    if "state" in carriers:
        keys.append(("state", origin))
    if "buffer" in carriers:
        nbuf = len(rec.get("buffers") or [])
        for j in range(nbuf):
            keys.append(("buffer", str(j)))
    if "flow" in carriers:
        keys.append(("flow", "throughput"))
        for k in ("sunk", "scrapped"):
            keys.append(("flow", k))
    return keys


def paired_z(
    fault: dict, seed: int, carriers: list[str], k: float = 3.0
) -> dict:
    """Max standardized deviation per carrier, fault-on vs fault-off.

    Baseline (mean/std) from the fault-off run's clean prefix — never
    from GT labels. Categorical states mapped to non-RUN indicator.
    Returns {"fired": bool, "tick": int|None, "per_carrier": {...}}.
    """
    from src.twin import run_episode

    origin = str(fault.get("origin"))
    t0 = int(fault.get("t0", 0))
    t1 = int(fault.get("t0", 0) + fault.get("dur", 0))
    rec_on = run_episode(seed, dict(fault))
    rec_off = run_episode(seed, None)
    per: dict[str, tuple[float, int | None]] = {}
    for kind, key in _carrier_keys(rec_on, origin, carriers):
        vo = _series(rec_on, kind, key)
        vf = _series(rec_off, kind, key)
        if vo is None or vf is None or len(vo) == 0:
            continue
        if kind in ("buffer", "flow") and not (
            kind == "flow" and key in ("sunk", "scrapped")
        ):
            # Count levels: Poisson-style totals test, not Gaussian z.
            # Single-blip "z=1e9 on sd=1e-9" artifacts must not fire.
            so = float(np.asarray(vo[t0:t1], dtype=float).sum()) if t1 > t0 else 0.0
            sf = float(np.asarray(vf[t0:t1], dtype=float).sum()) if t1 > t0 else 0.0
            need = max(3.0, 3.0 * max(sf, 1.0) ** 0.5)
            z = abs(so - sf) / max(need, 1e-9) * 3.0
            tick = t0 if abs(so - sf) >= need else None
            per[f"{kind}:{key}"] = (z if tick is not None else 0.0, tick)
            continue
        if kind == "state":
            vo = (np.asarray(vo) != "RUN").astype(float)
            vf = (np.asarray(vf) != "RUN").astype(float)
            tol = 0.5  # any occurrence (z explodes on all-RUN baselines)
        elif kind in ("buffer", "flow"):
            vo, vf = np.asarray(vo, dtype=float), np.asarray(vf, dtype=float)
            tol = 1.0  # one count/part (z explodes on constant counters)
        else:
            vo, vf = np.asarray(vo, dtype=float), np.asarray(vf, dtype=float)
            tol = 0.5  # native obs/current units (~0.5σ at base sigma ~1)
        lo = max(1, min(t0, len(vf)))
        mu, sd = float(vf[:lo].mean()), max(float(vf[:lo].std()), 1e-9)
        seg = (vo[t0:t1] - mu) / sd if t1 > t0 and t0 < len(vo) else np.array([0.0])
        raw = (vo[t0:t1] - mu) if t1 > t0 and t0 < len(vo) else np.array([0.0])
        if kind == "flow" and key in ("sunk", "scrapped"):
            seg = np.array([float(abs(seg[0]))]) if len(seg) else seg
            raw = np.array([float(abs(raw[0]))]) if len(raw) else raw
        zi = int(np.argmax(np.abs(seg))) if len(seg) else 0
        z = float(np.abs(seg).max()) if len(seg) else 0.0
        r = float(np.abs(raw).max()) if len(raw) else 0.0
        if r < tol:
            z = 0.0  # z-only fires on degenerate baselines don't count
        per[f"{kind}:{key}"] = (z, t0 + zi if len(seg) else None)
    best = max(per.values(), key=lambda v: v[0], default=(0.0, None))
    return {"fired": bool(best[0] >= k), "tick": best[1], "per_carrier": per}
