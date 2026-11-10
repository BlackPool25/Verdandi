"""Task 3: template reporter + citation checks (TDD RED)."""

import pytest


def _packet():
    return {
        "id": "det-1-160", "root": "B2", "onset": 150, "trigger": 160,
        "verdict": "diagnosed",
        "trace": [
            {"id": "ev-B2", "machine": "B2", "onset": 150, "onset_kind": "state", "own_state": "DOWN"},
            {"id": "ev-A1", "machine": "A1", "onset": 152, "onset_kind": "state", "own_state": "STARVED"},
        ],
        "paths": [{"id": "path-0", "nodes": ["B2", "A1"], "prob": 0.7}],
        "confidence": {"top1": 0.7},
        "flow": {},
    }


def _decision():
    return {"spec": "v1", "packet_id": "det-1-160", "machine": "B2",
            "machine_prob": 0.8, "fault_family": "drift", "family_prob": 0.75,
            "severity": "SEV3", "severity_prob": 0.9, "verdict": "decided"}


def test_card_cites_every_claim():
    from src.reporter import build_card

    card = build_card(_packet(), _decision())
    assert card["root"] == "B2" and card["severity"] == "SEV3"
    for claim in card["claims"]:
        assert claim["evidence_id"] in ("ev-B2", "ev-A1", "path-0", "det-1-160")


def test_numbers_verbatim_not_computed():
    from src.reporter import build_card

    card = build_card(_packet(), _decision())
    assert card["confidence"] == 0.7  # from packet, not recomputed
    assert card["machine_prob"] == 0.8  # from decision, not recomputed


def test_abstain_card_on_null_or_silent():
    from src.reporter import build_card

    d = dict(_decision(), verdict="abstain", machine=None)
    card = build_card(_packet(), d)
    assert card["verdict"] == "abstain" and card["root"] is None
    p = dict(_packet(), verdict="abstain", root=None, trace=[])
    card2 = build_card(p, d)
    assert card2["verdict"] == "abstain"


def test_dossier_has_full_trace():
    from src.reporter import build_dossier

    d = build_dossier(_packet(), _decision())
    assert [n["machine"] for n in d["nodes"]] == ["B2", "A1"]
    assert d["packet_id"] == "det-1-160"
