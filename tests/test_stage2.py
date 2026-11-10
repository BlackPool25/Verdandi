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


def test_serving_artifact_matches_builder_width():
    import numpy as np
    import pandas as pd
    from src.stage2 import load
    from src.twin import _MACHINE_ORDER

    import scripts.eval_stacked as es

    oof = pd.read_parquet("artifacts/oof_identity.parquet")
    _eps = oof.loc[oof["y"] == 1, "ep"].unique()[:20]
    oof = oof[oof["ep"].isin(_eps)]
    X, _, _, _ = es.build_rows(oof, list(_MACHINE_ORDER), None, None)
    bst = load("artifacts/stage2-rank.txt")
    assert bst.num_feature() == X.shape[1]
