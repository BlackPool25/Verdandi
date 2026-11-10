"""Task 2: Jev spec + client (TDD RED)."""

import pytest


def _packet():
    return {"id": "det-1-160", "root": "B2", "trigger": 160}


def _client_fixed(choice="B2", prob=0.8):
    class C:
        def ask(self, packet, questions, spec=None):
            assert spec == "v1"
            assert set(questions) >= {"machine", "family", "severity"}
            return {q: {"choice": choice, "probability": prob} for q in questions}

    return C()


def test_spec_pins_physics_criteria():
    from src import jev

    assert jev.JEV_SPEC == "v1"
    blob = str(jev.QUESTIONS)
    for kw in ("STARVED", "current unmoved", "REJECT_ROUTE", "SEV1"):
        assert kw in blob


def test_decide_maps_fixture():
    from src import jev

    d = jev.decide(_packet(), client=_client_fixed("B2", 0.8))
    assert d["machine"] == "B2" and d["verdict"] == "decided"
    assert d["packet_id"] == "det-1-160"


def test_null_or_low_conf_abstains():
    from src import jev

    assert jev.decide(_packet(), client=_client_fixed("null", 0.9))["verdict"] == "abstain"
    assert jev.decide(_packet(), client=_client_fixed("B2", 0.1))["verdict"] == "abstain"


def test_no_client_raises_for_fallback():
    from src import jev

    with pytest.raises(jev.JevUnavailable):
        jev.decide(_packet(), client=None)


def test_parse_tev_choice_after_think():
    from src.jev import parse_tev_choice

    text = "<think>long reasoning... Selection: B.</think>\n\nB"
    assert parse_tev_choice(text, ["A", "B", "C"]) == "B"
    assert parse_tev_choice("no letters here 123", ["A", "B"]) is None
    assert parse_tev_choice("<think>x</think>\nC", ["A", "B", "C"]) == "C"


def test_render_packet_state_deterministic():
    from src.jev import render_state

    p1 = {"id": "d", "trace": [
        {"id": "ev-B", "machine": "B", "onset": 5, "own_state": "DOWN"},
        {"id": "ev-A", "machine": "A", "onset": 7, "own_state": "RUN"}]}
    assert render_state(p1) == render_state(p1)
    assert "B" in render_state(p1) and "DOWN" in render_state(p1)
