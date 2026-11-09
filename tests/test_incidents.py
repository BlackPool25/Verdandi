"""Incident registry tests: link new triggers to open incidents, else open."""

import pytest


def _edges():
    return {"A0": ["A1"], "A1": ["A2"], "A2": [], "C0": []}


def test_links_reachable_later_trigger_to_open_incident():
    from src.incidents import Registry

    reg = Registry()
    reg.open("inc1", root="A0", onset=100, machines={"A0"})
    link = reg.link("A1", 104, edges=_edges(), bounds=(1, 6))
    assert link == "inc1"
    assert reg.get("inc1")["machines"] == {"A0", "A1"}


def test_opens_new_incident_when_unreachable():
    from src.incidents import Registry

    reg = Registry()
    reg.open("inc1", root="A0", onset=100, machines={"A0"})
    link = reg.link("C0", 150, edges=_edges(), bounds=(1, 6))
    assert link != "inc1"
    assert reg.get(link)["root"] == "C0"


def test_second_fault_flag_when_unexplained():
    from src.incidents import Registry

    reg = Registry()
    reg.open("inc1", root="A0", onset=100, machines={"A0"})
    # far-late trigger inside reachable set but outside delay bounds
    link, flag = reg.link("A2", 250, edges=_edges(), bounds=(1, 6), flag_second=True)
    assert link == "inc1" and flag == "possible-second-fault"


def test_closed_incident_does_not_link():
    from src.incidents import Registry

    reg = Registry()
    reg.open("inc1", root="A0", onset=100, machines={"A0"})
    reg.close("inc1")
    with pytest.raises(KeyError):
        reg.get("inc1")
    link = reg.link("A1", 104, edges=_edges(), bounds=(1, 6))
    assert link != "inc1"
