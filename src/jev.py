"""Jev decider: typed categorization over the evidence packet.

JEV_SPEC v1 criteria derive from measured failure physics (see
docs/ARCHITECTURE_JEV.md). The client is injectable: tests use recorded
fixtures; live API only when JEV_API_KEY is set, else JevUnavailable.
"""

from __future__ import annotations

JEV_SPEC = "v1"

QUESTIONS = {
    "machine": {
        "type": "choice",
        "instructions": "Which machine originated the fault? Use onset order and states.",
        "criteria": {
            "origin": "earliest onset with DOWN or counter state; never STARVED-only (symptom)",
        },
    },
    "family": {
        "type": "choice",
        "instructions": "Which fault family best explains the channel evidence?",
        "criteria": {
            "breakdown": "machine DOWN",
            "delay": "cycle stretch, timing shift only",
            "loss": "count/flow deficit, sunk/scrapped counters move",
            "quality": "sink rejects, REJECT_ROUTE events",
            "drift": "slow ramp in obs, EWMA accumulates",
            "bias": "obs offset, current unmoved (sensor-only)",
            "spike": "brief transient pulse",
        },
    },
    "severity": {
        "type": "choice",
        "instructions": "SEV1 line-down .. SEV5 single-window transient.",
        "criteria": {
            "SEV1": "line DOWN, flow stopped",
            "SEV2": "major degradation, multiple machines affected",
            "SEV3": "single-machine degradation, line running",
            "SEV4": "minor deviation, auto-recovered or stable",
            "SEV5": "single-window transient",
        },
    },
}


class JevUnavailable(RuntimeError):
    """Raised when no Jev client is configured (offline/template fallback)."""


def decide(packet: dict, client=None, threshold: float = 0.5) -> dict:
    """Typed decision over packet. Null (or conf < threshold) -> abstain."""
    if client is None:
        raise JevUnavailable("JEV_API_KEY not set; use template reporter")
    raw = client.ask(packet, QUESTIONS, spec=JEV_SPEC)
    out = {"spec": JEV_SPEC, "packet_id": packet.get("id")}
    for q in ("machine", "family", "severity"):
        r = raw.get(q, {}) if isinstance(raw, dict) else {}
        out[q] = r.get("choice")
        out[q + "_prob"] = float(r.get("probability", 0.0))
    if any(out[q] in (None, "null") or out[q + "_prob"] < threshold for q in ("machine", "family")):
        out["verdict"] = "abstain"
    else:
        out["verdict"] = "decided"
    return out
