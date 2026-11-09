

def test_quality_sink_all_routes_upstream_origin():
    from src import twin

    f = {"class": "quality", "origin": "B2", "t0": 150, "dur": 35,
         "mag_sigma": 5.0, "extra": {"reject_rate": 0.4}}
    base = twin.run_episode(5, f)
    assert sum(1 for e in base["events"] if e.get("event") == "REJECT_ROUTE") == 0
    f2 = {"class": "quality", "origin": "B2", "t0": 150, "dur": 35,
          "mag_sigma": 5.0, "extra": {"reject_rate": 0.4, "sink_all": True}}
    routed = twin.run_episode(5, f2)
    assert sum(1 for e in routed["events"] if e.get("event") == "REJECT_ROUTE") > 0
