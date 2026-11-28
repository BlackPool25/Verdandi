"""One-command e2e incident report (Task 8 / issue 73).

Chain (offline, hermetic, no bridge/SSE/frontend changes, no network):
  diagnose_incident (Task 7 calibrated gate, live)
    -> emit_packet v1 (IDs det-{ep}-{trigger} / ev-{machine} / path-{i})
    -> tev-or-template (template default; tev only if JEV_API_KEY is set,
       any tev failure falls back to template -- the key is never required)
    -> build_card / build_dossier (verbatim numbers, citation-checked)
    -> artifacts/incidents/<id>/{packet,decision,card,dossier}.json
       + card.md + incident.json (Task 1 scope code + reason + coverage)

Schemas frozen: packet/card/dossier shapes are exactly what emit_packet /
build_card / build_dossier return. Scope/reason/coverage live only in
incident.json + card.md, never inside the frozen dicts.

Scores note: diagnose_incident(..., scores=) injects per-machine detection
strength measured from the frame (max |z| over the post-trigger window), the
same role stage-2 scores play per docs/DIAGNOSIS_FLOW.md:123. The heuristic
_eweight fallback is untouched and still used with --no-scores (on synthetic
data it abstains through the live gate -- no forcing anywhere).
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd

# Task 1 scope codes (docs/SHIP_STATUS.md, task-1-report). Decided incidents
# ship; abstains map to the matching abstain_* code. abstain_weak_family /
# abstain_transfer / abstain_rerank are not produced by this script (no family
# model, no transfer slice, no rerank here) -- documented, not emitted.
SCOPE_DECIDED = "ship"
SCOPE_FOR_ABSTAIN = {
    "low-confidence-calibrated": "abstain_low_conf",
    "silent-clean": "abstain_sensor",
    "low-recall": "abstain_paths",
    "single-node": "abstain_paths",
    "tev-abstain": "abstain_tev",
}

EDGES = {"A0": ["B9"], "B9": []}
OBS_COLS = ["obs_A0", "obs_B9"]
TRIGGER_DEFAULT = 190


def make_frame(seed: int = 7, clean: bool = False, n: int = 300,
               a0_onset: int = 185, b9_onset: int = 195):
    """Deterministic 2-machine synthetic incident (numpy default_rng(seed)).

    Fault frame: A0 DOWN with a strong obs shift (origin), B9 STARVED with a
    weak obs drift (downstream symptom). Clean frame: pure noise, all RUN --
    the gate must abstain silent-clean, never guess.
    """
    rng = np.random.default_rng(seed)
    if clean:
        obs_a0 = rng.normal(0, 1, n)
        obs_b9 = rng.normal(0, 1, n)
        st_a0 = ["RUN"] * n
        st_b9 = ["RUN"] * n
        fault_family = None
    else:
        obs_a0 = np.concatenate(
            [rng.normal(0, 1, a0_onset), rng.normal(0, 1, n - a0_onset) + 8.0])
        obs_b9 = np.concatenate(
            [rng.normal(0, 1, b9_onset), rng.normal(0, 1, n - b9_onset) + 1.0])
        st_a0 = ["RUN"] * a0_onset + ["DOWN"] * (n - a0_onset)
        st_b9 = ["RUN"] * b9_onset + ["STARVED"] * (n - b9_onset)
        fault_family = "breakdown"
    g = pd.DataFrame({
        "episode_id": [1] * n,
        "step": list(range(n)),
        "obs_A0": obs_a0,
        "obs_B9": obs_b9,
        "state_A0": st_a0,
        "state_B9": st_b9,
    })
    return g, list(OBS_COLS), {k: list(v) for k, v in EDGES.items()}, fault_family


def measure_scores(g: pd.DataFrame, obs_cols: list[str], diag: list[dict],
                   trigger: int, window: int = 40) -> dict[str, float]:
    """Per-machine detection strength: max |prefix-z| over [trigger, +window).

    Measured from the frame (not invented): prefix median/MAD from the clean
    prefix, exactly like src.diagnose._znorm. Deterministic pure function.
    """
    from src.diagnose import _znorm

    scores: dict[str, float] = {}
    for r in diag:
        col = f"obs_{r['machine']}"
        if col not in g.columns or "step" not in g.columns:
            scores[r["machine"]] = 0.0
            continue
        v = g[col].to_numpy(dtype=float)
        z = np.abs(_znorm(v))
        steps = g["step"].to_numpy()
        sel = (steps >= trigger) & (steps < trigger + window)
        scores[r["machine"]] = float(z[sel].max()) if sel.any() else 0.0
    return scores


def build_flow(g: pd.DataFrame, diag: list[dict], trigger: int) -> dict:
    """Deterministic flow annotation: post-trigger window stats per machine."""
    flow: dict = {"trigger": int(trigger), "n_trace": len(diag)}
    for r in diag:
        col = f"obs_{r['machine']}"
        m = r["machine"]
        if col in g.columns and "step" in g.columns:
            steps = g["step"].to_numpy()
            seg = g[(steps >= trigger) & (steps < trigger + 8)][col].to_numpy(dtype=float)
            flow[m] = {
                "mean": round(float(seg.mean()), 6) if len(seg) else None,
                "n": int(len(seg)),
            }
        else:
            flow[m] = {"mean": None, "n": 0}
    return flow


def template_decision(packet: dict) -> dict:
    """Offline template decision: every number verbatim-copied from the packet.

    machine_prob / family_prob carry packet confidence top1 through unchanged
    (documented copy -- there is no separate severity/family model on the
    template path). Severity is a fixed category, not a measurement.
    """
    decided = packet.get("verdict") != "abstain" and packet.get("root") is not None
    top1 = (packet.get("confidence") or {}).get("top1")
    if not decided:
        return {
            "spec": "template-v1",
            "packet_id": packet.get("id"),
            "machine": None,
            "machine_prob": None,
            "fault_family": packet.get("fault_family"),
            "family_prob": None,
            "severity": None,
            "severity_prob": None,
            "verdict": "abstain",
        }
    return {
        "spec": "template-v1",
        "packet_id": packet.get("id"),
        "machine": packet.get("root"),
        "machine_prob": top1,
        "fault_family": packet.get("fault_family"),
        "family_prob": top1,
        "severity": "SEV3",
        "severity_prob": top1,
        "verdict": "decided",
    }


def decide_packet(packet: dict) -> tuple[dict, str]:
    """tev-or-template: tev only when JEV_API_KEY is set, else template.

    Any tev failure (no client, no route, abstain-worthy null) falls back to
    the template -- offline runs never touch the network. Returns
    (decision, via) with via in {"tev", "template"}.
    """
    if os.environ.get("JEV_API_KEY"):
        try:
            from src.jev import TevClient, decide

            decision = decide(packet, client=TevClient())
            if decision.get("verdict") != "abstain":
                return decision, "tev"
            decision = dict(decision, _tev_abstain=True)
            return decision, "tev"
        except Exception as exc:  # noqa: BLE001 - offline guarantee: any tev
            # failure (no route, timeout, bad payload) falls back to template.
            print(f"report_incident: tev decision failed "
                  f"({type(exc).__name__}: {exc}); falling back to template",
                  file=sys.stderr)
    return template_decision(packet), "template"


def _verify_verbatim(packet: dict, decision: dict, card: dict, dossier: dict) -> None:
    """Fail loud on any invented number: card/dossier must copy, never compute."""
    if card.get("verdict") == "decided":
        assert card["confidence"] == (packet.get("confidence") or {}).get("top1"), \
            "card confidence must verbatim-copy packet confidence top1"
        assert card["machine_prob"] == decision.get("machine_prob"), \
            "card machine_prob must verbatim-copy the decision"
    assert dossier.get("paths") == packet.get("paths"), \
        "dossier paths must verbatim-copy packet paths"
    assert dossier.get("confidence") == packet.get("confidence"), \
        "dossier confidence must verbatim-copy packet confidence"


def run_report(seed: int = 7, trigger: int = TRIGGER_DEFAULT, clean: bool = False,
               calibrator: dict | None = None, use_scores: bool = True,
               store=None) -> dict:
    """Full e2e: frame -> gated diagnosis -> packet -> decision -> card/dossier."""
    from src.calibration_artifact import load_calibrator
    from src.diagnose import diagnose_from_trigger, diagnose_incident
    from src.packet import emit_packet
    from src.reporter import build_card, build_dossier

    g, obs_cols, edges, fault_family = make_frame(seed=seed, clean=clean)
    ep = int(seed)
    cal = dict(calibrator) if calibrator is not None else load_calibrator()

    kept = diagnose_from_trigger(g, obs_cols, trigger, back=16)
    scores = measure_scores(g, obs_cols, kept, trigger) if (use_scores and kept) else None
    report = diagnose_incident(
        g, obs_cols, trigger, edges, store=store, seed=seed,
        fault_family=fault_family or "unknown",
        scores=scores, calibrator=cal)
    reason = report.get("abstain")

    paths = [(list(p), float(v)) for p, v in (report.get("paths") or [])]
    confidence = dict(report.get("confidence") or {})
    flow = build_flow(g, kept, trigger)
    top = kept[0] if kept else None
    sensor_verdict = top["coord_class"] if top else "abstain"

    if reason is None:
        packet = emit_packet(
            kept, trigger=trigger, sensor_verdict=sensor_verdict,
            fault_family=fault_family, ep=ep, paths=paths,
            confidence=confidence, flow=flow)
    else:
        # Abstain: no root guess (empty trace), but keep ranked paths +
        # confidence + flow so the dossier preserves the evidence.
        packet = emit_packet(
            [], trigger=trigger, sensor_verdict=sensor_verdict,
            fault_family=fault_family, ep=ep, paths=paths,
            confidence=confidence, flow=flow)

    decision, via = decide_packet(packet)
    if via == "tev" and decision.pop("_tev_abstain", False):
        reason = reason or "tev-abstain"
    card = build_card(packet, decision)
    dossier = build_dossier(packet, decision)
    _verify_verbatim(packet, decision, card, dossier)

    covered = reason is None
    scope = SCOPE_DECIDED if covered else SCOPE_FOR_ABSTAIN.get(reason, "abstain_low_conf")
    incident = {
        "incident_id": packet["id"],
        "seed": int(seed),
        "trigger": int(trigger),
        "clean": bool(clean),
        "fault_family": fault_family,
        "root": report.get("root"),
        "scope": scope,
        "reason": reason,
        "via": via,
        "scores_source": "measured-z" if use_scores else "heuristic-eweight",
        "scores_n": len(scores or {}),
        "coverage": {
            "covered": bool(covered),
            "conf": confidence.get("top1"),
            "tau": cal.get("tau"),
        },
        "calibrator": {"T": cal.get("T"), "tau": cal.get("tau"),
                       "risk_target": cal.get("risk_target")},
        "files": ["packet.json", "decision.json", "card.json",
                  "dossier.json", "card.md", "incident.json"],
    }
    return {"packet": packet, "decision": decision, "card": card,
            "dossier": dossier, "incident": incident, "via": via,
            "report": report}


def render_card_md(card: dict, packet: dict, incident: dict) -> str:
    """Deterministic operator card markdown (Task 9 viewer input)."""
    lines = [f"# Incident {incident['incident_id']}", ""]
    if card.get("verdict") == "abstain":
        lines += [
            "**ABSTAIN** -- collect more evidence",
            "",
            f"- reason: `{incident['reason']}`",
            f"- scope: `{incident['scope']}`",
            f"- coverage: covered={incident['coverage']['covered']} "
            f"conf={incident['coverage']['conf']} "
            f"tau={incident['coverage']['tau']}",
            f"- packet: `{packet.get('id')}`",
        ]
        for p in packet.get("paths", [])[:3]:
            lines.append(
                f"- path candidate {'->'.join(p.get('nodes', []))} "
                f"prob {p.get('prob')}")
        lines += [""]
        return "\n".join(lines)
    lines += [
        f"- root: **{card.get('root')}**",
        f"- severity: {card.get('severity')} "
        f"(family {card.get('fault_family')})",
        f"- confidence: {card.get('confidence')} "
        f"(machine_prob {card.get('machine_prob')})",
        f"- scope: `{incident['scope']}` via {incident['via']}",
        f"- packet: `{packet.get('id')}`",
        "",
        "## Claims (each cites packet evidence)",
        "",
        "| claim | value | evidence_id |",
        "|---|---|---|",
    ]
    for claim in card.get("claims", []):
        lines.append(
            f"| {claim.get('text')} | {claim.get('value')} | "
            f"`{claim.get('evidence_id')}` |")
    lines += ["", f"- action: {card.get('action')}", ""]
    return "\n".join(lines)


def write_bundle(bundle: dict, out_dir) -> list[str]:
    """Write packet/decision/card/dossier/incident JSON + card.md.

    sort_keys + indent=2 + trailing newline: byte-identical reruns.
    """
    import pathlib

    out = pathlib.Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    written = []
    for name, obj in (("packet.json", bundle["packet"]),
                      ("decision.json", bundle["decision"]),
                      ("card.json", bundle["card"]),
                      ("dossier.json", bundle["dossier"]),
                      ("incident.json", bundle["incident"])):
        path = out / name
        path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8")
        written.append(str(path))
    md_path = out / "card.md"
    md_path.write_text(
        render_card_md(bundle["card"], bundle["packet"], bundle["incident"]),
        encoding="utf-8")
    written.append(str(md_path))
    return written


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="e2e incident report (offline)")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--trigger", type=int, default=TRIGGER_DEFAULT)
    ap.add_argument("--clean", action="store_true",
                    help="fault-free frame: expect silent-clean abstain")
    ap.add_argument("--no-scores", action="store_true",
                    help="use heuristic _eweight fallback instead of measured scores")
    ap.add_argument("--out", default=None,
                    help="output dir (default artifacts/incidents/<packet id>)")
    args = ap.parse_args(argv)

    bundle = run_report(seed=args.seed, trigger=args.trigger,
                        clean=args.clean, use_scores=not args.no_scores)
    out = args.out or os.path.join("artifacts", "incidents",
                                   bundle["incident"]["incident_id"])
    write_bundle(bundle, out)
    print(f"wrote {out} scope={bundle['incident']['scope']} "
          f"reason={bundle['incident']['reason']} via={bundle['via']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
