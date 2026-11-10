"""Template reporter: operator card + engineer dossier (offline fallback).

Contract: every claim cites an evidence ID from the packet; numbers are
copied verbatim from packet/decision, never computed. Null/silent ->
abstain card, never a guess.
"""

from __future__ import annotations


def _ids(packet: dict) -> set[str]:
    out = {packet.get("id")}
    out |= {t.get("id") for t in packet.get("trace", [])}
    out |= {p.get("id") for p in packet.get("paths", [])}
    return {i for i in out if i}


def build_card(packet: dict, decision: dict) -> dict:
    """Operator card: what/where/severity/action + cited claims."""
    if decision.get("verdict") == "abstain" or packet.get("verdict") == "abstain":
        return {
            "verdict": "abstain", "root": None, "severity": None,
            "packet_id": packet.get("id"), "claims": [],
            "action": "collect more evidence",
        }
    trace0 = (packet.get("trace") or [{}])[0]
    claims = [
        {"text": "origin", "value": decision.get("machine"),
         "evidence_id": trace0.get("id")},
        {"text": "onset", "value": trace0.get("onset"),
         "evidence_id": trace0.get("id")},
        {"text": "causal path", "value": (packet.get("paths") or [{}])[0].get("nodes"),
         "evidence_id": (packet.get("paths") or [{"id": None}])[0].get("id")},
    ]
    valid = _ids(packet)
    assert all(c["evidence_id"] in valid for c in claims), "uncited claim"
    return {
        "verdict": "decided",
        "root": decision.get("machine"),
        "fault_family": decision.get("fault_family"),
        "severity": decision.get("severity"),
        "confidence": packet.get("confidence", {}).get("top1"),
        "machine_prob": decision.get("machine_prob"),
        "packet_id": packet.get("id"),
        "claims": claims,
        "action": "inspect root machine",
    }


def build_dossier(packet: dict, decision: dict) -> dict:
    """Engineer dossier: full trace + paths + decision, all IDs intact."""
    return {
        "packet_id": packet.get("id"),
        "decision": decision,
        "nodes": [
            {"machine": t.get("machine"), "onset": t.get("onset"),
             "onset_kind": t.get("onset_kind"), "evidence_id": t.get("id")}
            for t in packet.get("trace", [])
        ],
        "paths": packet.get("paths", []),
        "confidence": packet.get("confidence", {}),
        "flow": packet.get("flow", {}),
        "verdict": decision.get("verdict", packet.get("verdict")),
    }
