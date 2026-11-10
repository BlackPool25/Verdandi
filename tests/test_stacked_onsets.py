"""Stage-2 onset wiring (TDD RED): main must use onset/state features."""


def test_main_wires_onsets():
    import scripts.eval_stacked as es

    assert hasattr(es, "load_onsets"), "main must load onsets.parquet via load_onsets()"
    import inspect

    src = inspect.getsource(es.main)
    assert "load_onsets" in src and "onsets" in src


def test_direction_feats_down_weights_one():
    import pandas as pd
    from scripts.eval_stacked import _direction_feats

    ons = pd.DataFrame([{"ep": 1, "machine": "A0", "onset": 100,
                         "onset_kind": "state", "own_state": "DOWN"}])
    out = _direction_feats(ons, 1, ["A0", "B0"])
    assert out["A0"][0] == 1.0 and out["A0"][1] == 1.0
    assert out["B0"] == (0.0, 0.0, 0.0, 1.0)
