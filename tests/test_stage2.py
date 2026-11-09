"""Stage-2 artifact roundtrip (TDD RED)."""

import numpy as np


def test_stage2_roundtrip_scores():
    from src.stage2 import load, save, train_final

    rng = np.random.default_rng(0)
    X = np.vstack([rng.normal(0, 0.2, (3, 2)) + (np.array([3.0, 2.0]) if i == 0 else 0)
                   for _ in range(4) for i in range(3)])
    y = np.tile([1, 0, 0], 4)
    g = np.repeat([1, 2, 3, 4], 3)
    m = train_final(X, y, g)
    save(m, "/tmp/stage2_test.txt")
    m2 = load("/tmp/stage2_test.txt")
    from src.ranker import score_candidates

    a = score_candidates(m, X[:3])
    b = np.asarray(m2.predict(X[:3]))
    assert np.allclose(a, b) and np.argmax(a) == 0
