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
