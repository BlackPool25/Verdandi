"""Twin-fork cascade forecast (TDD RED)."""

from src.forecast import predict_cascade


def test_forecast_contains_root_and_hits_downstream():
    rows = predict_cascade(
        seed=0,
        fault={"origin": "B2", "class": "breakdown", "t0": 130, "dur": 40},
        t_det=130,
        h=120,
    )
    by_m = {m: t for m, t, _ in rows}
    assert "B2" in by_m
    assert by_m["B2"] >= 130
    assert len(rows) >= 1
