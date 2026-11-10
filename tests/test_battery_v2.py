"""Task 2: v2 battery flag — quality sink_all opt-in, frozen default untouched (TDD)."""


def test_sink_all_default_off():
    from scripts.gen_mass_battery import build_specs

    _, _, faults = build_specs(n_per_cell=2, n_clean=4, seed=0)
    qs = [f for f in faults.values() if f["class"] == "quality"]
    assert qs, "expected quality specs in grid"
    assert all(not f.get("extra", {}).get("sink_all", False) for f in qs)


def test_sink_all_opt_in():
    from scripts.gen_mass_battery import build_specs

    _, _, faults = build_specs(n_per_cell=2, n_clean=4, seed=0, sink_all_quality=True)
    qs = [f for f in faults.values() if f["class"] == "quality"]
    nq = [f for f in faults.values() if f["class"] != "quality"]
    assert qs and all(f.get("extra", {}).get("sink_all") is True for f in qs)
    assert all(not f.get("extra", {}).get("sink_all", False) for f in nq)


def test_couple_loss_opt_in():
    from scripts.gen_mass_battery import build_specs

    _, _, faults = build_specs(n_per_cell=2, n_clean=4, seed=0, couple_loss=True)
    ls = [f for f in faults.values() if f["class"] == "loss"]
    nl = [f for f in faults.values() if f["class"] != "loss"]
    assert ls and all(f.get("extra", {}).get("couple_loss") is True for f in ls)
    assert all(not f.get("extra", {}).get("couple_loss", False) for f in nl)


def test_couple_loss_default_off():
    from scripts.gen_mass_battery import build_specs

    _, _, faults = build_specs(n_per_cell=2, n_clean=4, seed=0)
    assert all(not f.get("extra", {}).get("couple_loss", False) for f in faults.values())
