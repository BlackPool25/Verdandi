"""Task 8 (73): report_incident e2e determinism (TDD RED).

Same seed -> byte-identical packet + card JSON (template path; abstain path
deterministic too). No network: JEV_API_KEY must be unset in this env.
"""

import json
import os

import pytest


def _read_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def test_template_path_byte_identical(tmp_path):
    from scripts.report_incident import run_report, write_bundle

    assert "JEV_API_KEY" not in os.environ, "determinism test requires template path"
    r1 = run_report(seed=7)
    r2 = run_report(seed=7)
    assert r1["via"] == "template"
    assert r1["packet"] == r2["packet"]
    assert r1["card"] == r2["card"]
    assert r1["dossier"] == r2["dossier"]
    d1, d2 = tmp_path / "a", tmp_path / "b"
    write_bundle(r1, d1)
    write_bundle(r2, d2)
    for name in ("packet.json", "decision.json", "card.json",
                 "dossier.json", "card.md", "incident.json"):
        assert (d1 / name).read_bytes() == (d2 / name).read_bytes(), name


def test_abstain_path_deterministic_with_reason_and_coverage(tmp_path):
    from scripts.report_incident import run_report, write_bundle

    r1 = run_report(seed=7, clean=True)
    r2 = run_report(seed=7, clean=True)
    assert r1["packet"] == r2["packet"]
    assert r1["card"]["verdict"] == "abstain"
    assert r1["card"]["root"] is None
    manifest = r1["incident"]
    assert manifest["reason"], "abstain must carry a reason"
    assert "coverage" in manifest and manifest["coverage"]["covered"] is False
    d1, d2 = tmp_path / "a", tmp_path / "b"
    write_bundle(r1, d1)
    write_bundle(r2, d2)
    for name in ("packet.json", "card.json", "dossier.json",
                 "card.md", "incident.json"):
        assert (d1 / name).read_bytes() == (d2 / name).read_bytes(), name


def test_card_numbers_verbatim_not_computed():
    from scripts.report_incident import run_report

    r = run_report(seed=7)
    packet, decision, card, dossier = (
        r["packet"], r["decision"], r["card"], r["dossier"])
    assert card["verdict"] == "decided", f"expected decided sample, got {r['incident']}"
    assert card["confidence"] == packet["confidence"]["top1"]
    assert card["machine_prob"] == decision["machine_prob"]
    assert dossier["paths"] == packet["paths"]
    for prob_p, prob_d in zip(
            [p["prob"] for p in packet["paths"]],
            [p["prob"] for p in dossier["paths"]]):
        assert prob_p == prob_d
    valid = {packet["id"]}
    valid |= {t["id"] for t in packet["trace"]}
    valid |= {p["id"] for p in packet["paths"]}
    for claim in card["claims"]:
        assert claim["evidence_id"] in valid
