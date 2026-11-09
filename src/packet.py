"""Evidence packet: minimal dict the report layer consumes.

Input is diagnose_from_trigger output (ranked candidates) plus the
trigger/sensor/family context the harness already computes. No GT inside.
"""

from __future__ import annotations


def emit_packet(
    diag: list[dict],
    *,
    trigger: int,
    sensor_verdict: str,
    fault_family: str | None,
    onset_err_tol: int = 10,
) -> dict:
    """Build the evidence packet. Empty diag -> abstain verdict."""
    if not diag:
        return {
            "root": None,
            "onset": None,
            "trigger": int(trigger),
            "sensor_verdict": sensor_verdict,
            "fault_family": fault_family,
            "verdict": "abstain",
            "trace": [],
        }
    top = diag[0]
    return {
        "root": top["machine"],
        "onset": int(top["onset"]),
        "trigger": int(trigger),
        "sensor_verdict": sensor_verdict,
        "fault_family": fault_family,
        "verdict": "diagnosed",
        "onset_kind": top.get("onset_kind"),
        "own_state": top.get("own_state"),
        "trace": [
            {
                "machine": r["machine"],
                "onset": int(r["onset"]),
                "onset_kind": r.get("onset_kind"),
                "hop_est": int(r.get("hop_est", -1)),
            }
            for r in diag
        ],
    }
