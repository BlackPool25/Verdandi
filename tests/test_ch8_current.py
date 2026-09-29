"""CH8 current tables_resolve (Todo W1, TDD RED-first).

Example amps (A2/C2 15A, RWK0 3.5A) are ASSUMPTIONS for QA pinning,
not normative spec claims — owner sign-off gates merge (plan G4).
"""

import pytest

from src.config import (
    I_IDLE_RATIO,
    I_RATED_BY_CLASS,
    K_BY_GROUP,
    MACHINE_INDEX,
    MACHINES,
    STEP_SECONDS,
    VOLT,
    resolve_current,
)


def test_tables_resolve():
    # Scalars present with locked values.
    assert I_IDLE_RATIO == 0.15
    assert STEP_SECONDS == 1
    assert VOLT == 400

    # 9 classes keyed like TEMP_RANGES pattern.
    assert set(I_RATED_BY_CLASS) == {
        "feed",
        "form",
        "process",
        "finish",
        "inspect-tail",
        "assembly-kit",
        "assembly-join",
        "test",
        "rework",
    }

    # Every MACHINE_INDEX entry resolves both I_RATED and K.
    for name in MACHINE_INDEX:
        i_rated, k = resolve_current(name)
        assert isinstance(i_rated, float) and i_rated > 0
        assert isinstance(k, float) and 0 < k <= 1.0
        # Cross-check class table drives I_RATED.
        assert i_rated == float(I_RATED_BY_CLASS[MACHINES[name]["class"]])

    # QA happy pins (ASSUMPTIONS, not normative):
    assert resolve_current("A2") == (15.0, 1.0)  # assumption: process 15A
    assert resolve_current("C2") == (15.0, 0.7)  # assumption: process 15A, C-group k=0.7
    assert resolve_current("RWK0") == (3.5, 0.3)  # assumption: rework 3.5A, RWK k=0.3

    # K group spot checks.
    assert K_BY_GROUP["A"] == 1.0
    assert K_BY_GROUP["C"] == 0.7

    # Failure modes.
    with pytest.raises((KeyError, ValueError)):
        resolve_current("ZZZ9")  # unknown prefix/machine
    with pytest.raises((TypeError, ValueError)):
        resolve_current("A2", i_rated=99.0)  # v1: no per-machine override
