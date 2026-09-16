"""T1 bridge validation-mirror tests (failing-first, TDD red).

Every twin-mirror case asserts the bridge 422 body carries the twin's
error TEXT verbatim (computed live from src.twin._validate), so any
drift between bridge and twin fails loudly here.
"""

from fastapi.testclient import TestClient

from services.sim_bridge.app import app
from src.twin import _validate as twin_validate

client = TestClient(app)


def twin_text(seed, fault):
    try:
        twin_validate(seed, fault)
    except (ValueError, TypeError) as e:
        return str(e)
    raise AssertionError("twin unexpectedly accepted input")


def test_health_200():
    r = client.get("/health")
    assert r.status_code == 200


def test_happy_seed_only_returns_episode_id():
    r = client.post("/episode", json={"seed": 7})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["episode_id"]
    assert body["enable_natural_breakdown"] is True


def test_t0_119_rejected_with_twin_text():
    fault = {"class": "breakdown", "origin": "B2", "t0": 119, "dur": 10}
    r = client.post("/episode", json={"seed": 7, "faults": [fault]})
    assert 400 <= r.status_code < 500
    assert twin_text(7, [fault]) in r.json()["detail"]


def test_unknown_origin_rejected_with_twin_text():
    fault = {"class": "breakdown", "origin": "ZZ9", "t0": 150, "dur": 10}
    r = client.post("/episode", json={"seed": 7, "faults": [fault]})
    assert 400 <= r.status_code < 500
    assert twin_text(7, [fault]) in r.json()["detail"]


def test_unknown_class_rejected_with_twin_text():
    fault = {"class": "meltdown", "origin": "B2", "t0": 150, "dur": 10}
    r = client.post("/episode", json={"seed": 7, "faults": [fault]})
    assert 400 <= r.status_code < 500
    assert twin_text(7, [fault]) in r.json()["detail"]


def test_window_overflow_rejected_with_twin_text():
    fault = {"class": "drift", "origin": "B2", "t0": 295, "dur": 10}
    r = client.post("/episode", json={"seed": 7, "faults": [fault]})
    assert 400 <= r.status_code < 500
    assert twin_text(7, [fault]) in r.json()["detail"]


def test_same_machine_gap_lt5_rejected_with_twin_text():
    faults = [
        {"class": "drift", "origin": "B2", "t0": 150, "dur": 10},
        {"class": "bias", "origin": "B2", "t0": 162, "dur": 10},
    ]
    r = client.post("/episode", json={"seed": 7, "faults": faults})
    assert 400 <= r.status_code < 500
    assert twin_text(7, faults) in r.json()["detail"]


def test_negative_seed_rejected_with_twin_text():
    r = client.post("/episode", json={"seed": -1})
    assert 400 <= r.status_code < 500
    assert twin_text(-1, None) in r.json()["detail"]


def test_extra_non_dict_rejected_with_twin_text():
    fault = {"class": "drift", "origin": "B2", "t0": 150, "dur": 10, "extra": [1]}
    r = client.post("/episode", json={"seed": 7, "faults": [fault]})
    assert 400 <= r.status_code < 500
    assert twin_text(7, [fault]) in r.json()["detail"]


def test_stuck_normalized_to_breakdown():
    fault = {"class": "STUCK", "origin": "B2", "t0": 150, "dur": 10}
    r = client.post("/episode", json={"seed": 7, "faults": [fault]})
    assert r.status_code == 200, r.text
    assert r.json()["faults"][0]["class"] == "breakdown"


def test_quality_at_b9_accepted_with_noop_warning():
    fault = {"class": "quality", "origin": "B9", "t0": 150, "dur": 10}
    r = client.post("/episode", json={"seed": 7, "faults": [fault]})
    assert r.status_code == 200, r.text
    assert r.json()["noop_warning"] is True


def test_quality_at_asm2_no_warning():
    fault = {"class": "quality", "origin": "ASM2", "t0": 150, "dur": 10}
    r = client.post("/episode", json={"seed": 7, "faults": [fault]})
    assert r.status_code == 200, r.text
    assert r.json()["noop_warning"] is False


def test_enable_natural_breakdown_round_trip():
    r = client.post("/episode", json={"seed": 7, "enable_natural_breakdown": False})
    assert r.status_code == 200, r.text
    assert r.json()["enable_natural_breakdown"] is False


def test_single_dict_fault_accepted():
    r = client.post(
        "/episode",
        json={"seed": 7, "faults": {"class": "drift", "origin": "B2", "t0": 150, "dur": 10}},
    )
    assert r.status_code == 200, r.text


def test_bridge_strict_dur_below_range():
    fault = {"class": "drift", "origin": "B2", "t0": 150, "dur": 3}
    r = client.post("/episode", json={"seed": 7, "faults": [fault]})
    assert r.status_code == 422, r.text
    assert "bridge-strict (superset of twin)" in r.json()["detail"]


def test_bridge_strict_mag_out_of_range():
    fault = {"class": "drift", "origin": "B2", "t0": 150, "dur": 10, "mag_sigma": 99.0}
    r = client.post("/episode", json={"seed": 7, "faults": [fault]})
    assert r.status_code == 422, r.text
    assert "bridge-strict (superset of twin)" in r.json()["detail"]


def test_bridge_strict_delay_d_out_of_range():
    fault = {
        "class": "delay",
        "origin": "A7",
        "t0": 150,
        "dur": 10,
        "extra": {"d": 99},
    }
    r = client.post("/episode", json={"seed": 7, "faults": [fault]})
    assert r.status_code == 422, r.text
    assert "bridge-strict (superset of twin)" in r.json()["detail"]


def test_bridge_strict_drop_rate_out_of_range():
    fault = {
        "class": "loss",
        "origin": "B7P",
        "t0": 150,
        "dur": 10,
        "extra": {"drop_rate": 0.99},
    }
    r = client.post("/episode", json={"seed": 7, "faults": [fault]})
    assert r.status_code == 422, r.text
    assert "bridge-strict (superset of twin)" in r.json()["detail"]


def test_bridge_strict_mttr_mult_out_of_range():
    fault = {
        "class": "breakdown",
        "origin": "B2",
        "t0": 150,
        "dur": 10,
        "extra": {"mttr_mult": 99.0},
    }
    r = client.post("/episode", json={"seed": 7, "faults": [fault]})
    assert r.status_code == 422, r.text
    assert "bridge-strict (superset of twin)" in r.json()["detail"]


def test_bridge_strict_reject_rate_out_of_range():
    fault = {
        "class": "quality",
        "origin": "ASM2",
        "t0": 150,
        "dur": 10,
        "extra": {"reject_rate": 0.99},
    }
    r = client.post("/episode", json={"seed": 7, "faults": [fault]})
    assert r.status_code == 422, r.text
    assert "bridge-strict (superset of twin)" in r.json()["detail"]
