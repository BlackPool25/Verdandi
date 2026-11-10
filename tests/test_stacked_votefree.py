"""Vote-free ranker rows (Task 1, behavioral — no source-text asserts)."""

import numpy as np
import pandas as pd


def _syn_oof(n_ep=6, seed=0):
    from src.twin import _MACHINE_ORDER

    rng = np.random.default_rng(seed)
    machines = list(_MACHINE_ORDER)[:6]
    rows = []
    for ep in range(n_ep):
        root = machines[ep % len(machines)]
        for wi in range(8):
            pred = root if wi < 5 else "none"
            r = {"ep": ep, "pred": pred, "y": 1, "root": root, "fam": "drift"}
            for m in machines:
                r[f"proba_{m}"] = 0.7 if m == pred and pred != "none" else 0.05
            rows.append(r)
    return pd.DataFrame(rows), machines


def test_rows_free_shape():
    import scripts.eval_stacked as es

    oof, machines = _syn_oof()
    X, y, groups, fam = es.build_rows_free(oof, machines)
    assert X.shape == (len(machines) * 6, 2 + 4 + len(machines))
    assert set(np.unique(groups)) == set(range(6))
    assert y.sum() == 6  # one root per episode


def test_rows_free_ignores_teacher_proba():
    import scripts.eval_stacked as es

    oof, machines = _syn_oof()
    X1, _, _, _ = es.build_rows_free(oof, machines)
    oof2 = oof.copy()
    pcols = [c for c in oof.columns if c.startswith("proba_")]
    vals = oof2[pcols].to_numpy()
    oof2[pcols] = vals[:, ::-1]  # permute teacher posteriors
    oof2["pred"] = np.random.default_rng(1).permutation(oof2["pred"].to_numpy())
    X2, _, _, _ = es.build_rows_free(oof2, machines)
    assert np.array_equal(X1, X2)  # teacher outputs cannot move vote-free rows


def test_rows_free_no_onehot_ablation():
    import scripts.eval_stacked as es

    oof, machines = _syn_oof()
    X, _, _, _ = es.build_rows_free(oof, machines, include_onehot=False)
    assert X.shape == (len(machines) * 6, 2 + 4)


def test_free_eval_runs():
    import scripts.eval_stacked as es

    assert callable(es.main_free)


def _syn_flowmap(eps=(0, 1), machines=("A0", "A1")):
    return {(ep, m): [float(ep + 1), float(2 * (ep + 1))] for ep in eps for m in machines}


def test_rows_hybrid_shape_and_flow():
    import scripts.eval_stacked as es

    oof, machines = _syn_oof()
    fm = _syn_flowmap(range(6), machines)
    X, y, groups, fam = es.build_rows_hybrid(oof, machines, None, None, fm)
    n = len(machines)
    assert X.shape == (n * 6, 8 + 4 + n + 2)
    assert y.sum() == 6


def test_rows_hybrid_flow_moves_rows():
    import scripts.eval_stacked as es

    oof, machines = _syn_oof()
    fm = _syn_flowmap(range(6), machines)
    X1, _, _, _ = es.build_rows_hybrid(oof, machines, None, None, fm)
    fm2 = {(ep, m): [99.0, 99.0] for ep in range(6) for m in machines}
    X2, _, _, _ = es.build_rows_hybrid(oof, machines, None, None, fm2)
    assert not (X1 == X2).all()
