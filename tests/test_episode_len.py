"""Long-episode override tests: default T frozen, opt-in longer runs."""


def test_default_episode_length_unchanged():
    from src import twin

    rec = twin.run_episode(777, None)
    assert rec["T"] == 300
    assert all(len(row) == 300 for row in rec["obs"])


def test_long_episode_override_length_and_determinism():
    from src import twin

    a = twin.run_episode(777, None, episode_len=1000)
    b = twin.run_episode(777, None, episode_len=1000)
    assert a["T"] == 1000
    assert all(len(row) == 1000 for row in a["obs"])
    assert a["obs"] == b["obs"]
    # global default untouched by the override path
    from src import config

    assert config.T == 300
    assert twin.run_episode(777, None)["T"] == 300


def test_long_episode_accepts_late_fault():
    from src import twin

    f = {"class": "bias", "origin": "B2", "t0": 800, "dur": 12, "mag_sigma": 5.0}
    rec = twin.run_episode(777, f, episode_len=1000)
    assert rec["T"] == 1000
    assert sum(1 for s in rec["states"][0] if s == "RUN") > 0


def test_build_faults_spreads_over_long_horizon():
    from src import twin

    rows = twin.build_faults(12345, episode_len=1000)
    t0s = [r["t0"] for r in rows if not r.get("rep")]
    assert max(t0s) > 500
    assert all(120 <= t <= 1000 - 8 for t in t0s)
