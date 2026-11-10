"""Task 1: parameterized cache/fire_flow paths (TDD RED)."""


def test_entry_points_accept_overrides():
    import inspect

    import scripts.cache_windows as cw
    import scripts.eval_fire_flow as ef

    assert cw.CACHE_DIR == "artifacts/window_cache"
    assert ef.CACHE == "artifacts/window_cache"
    assert "glob" in inspect.signature(cw.main).parameters
    assert "out" in inspect.signature(cw.main).parameters
    assert "cache" in inspect.signature(ef.main).parameters
