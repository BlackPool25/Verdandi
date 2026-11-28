"""Task 8 (73): report_incident e2e determinism (TDD RED).

Same seed -> byte-identical packet + card JSON (template path; abstain path
deterministic too). No network: JEV_API_KEY must be unset in this env.
"""

import json
import os
import pathlib
import subprocess
import sys

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
BUNDLE_FILES = ("packet.json", "decision.json", "card.json",
                "dossier.json", "card.md", "incident.json")


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


def test_cli_two_processes_byte_identical(tmp_path):
    """Review (1): the one-command e2e claim needs a two-process regression.

    Runs scripts/report_incident.py in two separate CLI subprocesses (clean
    env, JEV_API_KEY stripped) and byte-compares all 6 bundle files. Catches
    hash-randomization, cwd/env dependence, and CLI plumbing drift that the
    in-process test cannot see.
    """
    assert "JEV_API_KEY" not in os.environ, "CLI test requires template path"
    script = REPO_ROOT / "scripts" / "report_incident.py"
    outs = [tmp_path / "a", tmp_path / "b"]
    for out in outs:
        env = {k: v for k, v in os.environ.items() if k != "JEV_API_KEY"}
        p = subprocess.run(
            [sys.executable, str(script), "--seed", "7", "--out", str(out)],
            cwd=str(REPO_ROOT), env=env, capture_output=True, text=True,
            timeout=300)
        assert p.returncode == 0, p.stderr
    for name in BUNDLE_FILES:
        assert (outs[0] / name).read_bytes() == (outs[1] / name).read_bytes(), name


def test_no_scores_abstains_low_conf():
    """Review (2): --no-scores (heuristic _eweight) must abstain live-gated."""
    from scripts.report_incident import run_report

    r = run_report(seed=7, use_scores=False)
    assert r["via"] == "template"
    assert r["card"]["verdict"] == "abstain"
    assert r["card"]["root"] is None
    assert r["incident"]["reason"] == "low-confidence-calibrated"
    assert r["incident"]["scope"] == "abstain_low_conf"
    assert r["incident"]["coverage"]["covered"] is False


def test_incident_records_scores_source():
    """Review (2a): incident.json must say which score source fed the gate."""
    from scripts.report_incident import run_report

    scored = run_report(seed=7)
    assert scored["incident"]["scores_source"] == "measured-z"
    heuristic = run_report(seed=7, use_scores=False)
    assert heuristic["incident"]["scores_source"] == "heuristic-eweight"


def test_tev_failure_falls_back_to_template_with_warning(monkeypatch, capsys):
    """Bare-except RED: tev blowup must fall back loudly, never silently."""
    import sys

    import src.jev as jev
    from scripts.report_incident import decide_packet, template_decision

    packet = {"id": "det-1-160", "verdict": "diagnosed", "root": "A0",
              "confidence": {"top1": 0.9}, "fault_family": "breakdown"}

    class _Boom:
        def ask(self, *a, **k):
            raise ConnectionError("simulated tev outage")

    monkeypatch.setenv("JEV_API_KEY", "test-key")
    monkeypatch.setattr(jev, "TevClient", lambda: _Boom())
    decision, via = decide_packet(packet)
    assert via == "template"
    assert decision == template_decision(packet)
    err = capsys.readouterr().err
    assert "tev" in err.lower(), "tev fallback must log a warning to stderr"
