"""Incident store link-or-create (TDD RED)."""

from src.incidents_store import IncidentStore


def test_link_downstream_to_open_incident():
    s = IncidentStore.memory()
    inc = s.create_incident("B2", "breakdown", t0_est=100, seed=1)
    s.save_prediction(inc, [("B7P", 108, 1), ("B8", 115, 2)])
    got, linked = s.link_or_create(
        machine="B8", onset_tick=116, own_state="STARVED", seed=1, h=150, slack=25
    )
    assert linked is True and got == inc


def test_unrelated_machine_creates_new_incident():
    s = IncidentStore.memory()
    inc = s.create_incident("B2", "breakdown", t0_est=100, seed=1)
    s.save_prediction(inc, [("B7P", 108, 1)])
    got, linked = s.link_or_create(
        machine="PKG1", onset_tick=110, own_state="DOWN", seed=1, h=150, slack=25
    )
    assert linked is False and got != inc
