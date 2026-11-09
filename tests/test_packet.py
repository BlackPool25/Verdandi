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
