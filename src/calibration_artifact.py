"""Calibration artifact loader + serve-time confidence (Task 7, PRISSUE-61).

Margin convention (byte-identical fit/serve): margin = top1-top2 of
T-scaled candidate probs. Scaling is done as p^(1/T) renormalization,
exactly equal to softmax(z/T) given p = softmax(z), without touching
rank_nodes. For any T > 0 this preserves argmax (kill-bar principle).

The served (a, b) are fit on teacher-window margins; at serve time the
same function is applied to rank_nodes possibility probs. Platt is
monotone in margin (a > 0), so the gate is exactly a margin threshold
with a probabilistic reading; incident-level absolute calibration on
heuristic margins is NOT claimed (see artifacts/calibration.json
scope_note, research R2).
"""

from __future__ import annotations

import warnings

_DEFAULT_PATH = "artifacts/calibration.json"


def load_calibrator(path: str = _DEFAULT_PATH) -> dict:
    """Load {T, a, b, tau, risk_target} from a JSON artifact.

    Missing/unreadable file -> identity fallback (T=1.0, gate open via
    tau=-inf) + warning. Never raises (keeps hermetic/offline tests green).
    """
    try:
        import json

        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
        return {
            "T": float(raw["T"]),
            "a": float(raw["a"]),
            "b": float(raw["b"]),
            "tau": float(raw["tau"]),
            "risk_target": float(raw.get("risk_target", 0.3)),
        }
    except (OSError, ValueError, KeyError, TypeError) as exc:  # never raise
        warnings.warn(f"calibrator artifact unreadable ({path}): {exc}; gate open")
        return {"T": 1.0, "a": 0.0, "b": 0.0, "tau": float("-inf"),
                "risk_target": 0.3}


def scaled_margin(probs: dict, T: float) -> tuple[float, object]:
    """(margin, top_key) of T-scaled probs; order-identical to unscaled."""
    if not probs:
        return 0.0, None
    tot_raw = sum(float(v) for v in probs.values())
    if not tot_raw > 0:
        return 0.0, next(iter(probs))
    T = max(float(T), 1e-12)
    w = {k: float(v) ** (1.0 / T) for k, v in probs.items()}
    tot = sum(w.values()) or 1.0
    s = sorted(w.items(), key=lambda kv: -kv[1])
    top1, top2 = s[0][1] / tot, (s[1][1] / tot if len(s) > 1 else 0.0)
    return float(top1 - top2), s[0][0]


def calibrated_conf(probs: dict, T: float, a: float, b: float) -> tuple[float, float]:
    """(conf, margin): Platt P(correct) on the T-scaled top1-top2 margin."""
    from src.confidence import platt_predict

    margin, _ = scaled_margin(probs, T)
    conf = float(platt_predict(margin, a, b))
    return conf, margin
