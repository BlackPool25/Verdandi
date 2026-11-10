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
    ep: int | None = None,
    paths: list[tuple[list[str], float]] | None = None,
    confidence: dict | None = None,
    flow: dict | None = None,
) -> dict:
    """Build the evidence packet (schema v1). Empty diag -> abstain verdict.

    Every field carries an id: packet `det-{ep}-{trigger}`, per-machine
    `ev-{machine}`, ranked paths `path-{i}`. Pure function of inputs.
    """
    pid = f"det-{ep}-{int(trigger)}" if ep is not None else f"det-{int(trigger)}"
    if not diag:
        return {
            "id": pid,
            "root": None,
            "onset": None,
            "trigger": int(trigger),
            "sensor_verdict": sensor_verdict,
            "fault_family": fault_family,
            "verdict": "abstain",
            "trace": [],
            "paths": [],
            "confidence": confidence or {},
            "flow": flow or {},
        }
    top = diag[0]
    return {
        "id": pid,
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
                "id": f"ev-{r['machine']}",
                "machine": r["machine"],
                "onset": int(r["onset"]),
                "onset_kind": r.get("onset_kind"),
                "own_state": r.get("own_state"),
                "hop_est": int(r.get("hop_est", -1)),
                "evidence": r.get("evidence", ""),
            }
            for r in diag
        ],
        "paths": [
            {"id": f"path-{i}", "nodes": list(p), "prob": float(v)}
            for i, (p, v) in enumerate(paths or [])
        ],
        "confidence": confidence or {},
        "flow": flow or {},
    }
