"""Evidence packet tests: minimal dict the report layer consumes."""



def test_packet_minimal_fields():
    from src.packet import emit_packet

    diag = [
        {"machine": "B2", "onset": 150, "onset_kind": "state", "own_state": "DOWN", "hop_est": 0},
        {"machine": "A1", "onset": 152, "onset_kind": "state", "own_state": "STARVED", "hop_est": 1},
    ]
    p = emit_packet(diag, trigger=160, sensor_verdict="process", fault_family="drift")
    assert p["root"] == "B2"
    assert p["onset"] == 150
    assert p["trigger"] == 160
    assert p["sensor_verdict"] == "process"
    assert p["fault_family"] == "drift"
    assert len(p["trace"]) == 2
    assert p["trace"][0]["hop_est"] == 0


def test_packet_empty_diag_abstains():
    from src.packet import emit_packet

    p = emit_packet([], trigger=160, sensor_verdict="abstain", fault_family=None)
    assert p["root"] is None
    assert p["verdict"] == "abstain"


def test_packet_v1_ids_and_determinism():
    from src.packet import emit_packet

    diag = [
        {"machine": "B2", "onset": 150, "onset_kind": "state", "own_state": "DOWN", "hop_est": 0},
        {"machine": "A1", "onset": 152, "onset_kind": "state", "own_state": "STARVED", "hop_est": 1},
    ]
    kw = dict(trigger=160, sensor_verdict="process", fault_family="drift", ep=45200,
              paths=[(["B2", "A1"], 0.7)], confidence={"top1": 0.7, "T": 2.58},
              flow={"B2": {"sunk": 3}})
    p1 = emit_packet(diag, **kw)
    p2 = emit_packet(diag, **kw)
    assert p1 == p2  # deterministic
    assert p1["id"] == "det-45200-160"
    assert all("id" in t for t in p1["trace"])  # ev- IDs
    assert p1["trace"][0]["id"] == "ev-B2"
    assert p1["paths"][0]["id"] == "path-0"
    assert p1["confidence"]["top1"] == 0.7
