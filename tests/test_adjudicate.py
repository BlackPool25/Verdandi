"""H-wire adjudication tests (synthetic; real numbers in Task 17 run)."""

from __future__ import annotations

from scripts.adjudicate_h_wires import adjudicate


def test_adjudication_calls_survived_and_falsified():
    rows = adjudicate(
        {"id": "H9", "metric": 0.9, "bar": 0.8, "higher_is_better": True},
        {"id": "H8", "metric": 0.1, "bar": 0.8, "higher_is_better": True},
        battery_id="test",
    )
    assert {r["status"] for r in rows} == {"Survived", "Falsified"}
    assert all(r["battery_id"] == "test" and r["date"] for r in rows)
