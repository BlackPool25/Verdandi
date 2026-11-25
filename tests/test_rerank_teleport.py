"""Task 5 RED: calibrated rerank (63) + flow-teleport PPR (64).

Variant 1 = post-hoc calibrated rerank on stage2-oof.npz (identical
episodes/groups/CV — T scaling must preserve forced top-1 by theory).
Variant 2 = single truncation-config change, identical splits.
PPR teleport = ranker-softmax x flow mass, alpha=0.85 default.
"""

import numpy as np


def test_calibrated_rerank_identical_episodes_dual_report():
    import scripts.eval_stacked as es

    z = np.load("artifacts/stage2-oof.npz", allow_pickle=True)
    votable = es.votable_episodes()
    out = es.rerank_top1(z["oof_pred"], z["y"], z["groups"], temperature=1.0,
                         votable=votable)
    assert out["votable_n"] == 2712, out
    assert out["pooled_n"] == 4200, out
    assert abs(out["votable_top1"] - 0.667) < 0.001, out
    assert abs(out["pooled_top1"] - 0.461) < 0.001, out
    # T-scaling is monotonic per episode: argmax (forced top-1) preserved.
    cal = es.rerank_top1(z["oof_pred"], z["y"], z["groups"], temperature=0.168,
                         votable=votable)
    assert cal["votable_top1"] == out["votable_top1"], (cal, out)
    assert cal["pooled_top1"] == out["pooled_top1"], (cal, out)


def test_variant2_identical_splits_to_baseline():
    import scripts.eval_stacked as es

    z = np.load("artifacts/stage2-oof.npz", allow_pickle=True)
    y, groups, fam = z["y"], z["groups"], z["fam"]
    rng = np.random.default_rng(0)
    X = rng.normal(size=(len(y), 4))
    a = es.run_variant_lambdarank(X, y, groups, fam, seed=0)
    b = es._run_lambdarank(X, y, groups, fam, seed=0, return_folds=True)
    assert a["fold_eps"] == b["fold_eps"], "variant-2 must reuse baseline splits"
    assert len(a["oof_pred"]) == len(y)


def test_flow_teleport_blend_math():
    from src.possibility import flow_teleport

    probs = {"A0": 0.7, "A1": 0.2, "A2": 0.1}
    flow = {"A0": 5.0, "A1": 5.0, "A2": 5.0}
    out = flow_teleport(probs, flow)  # default alpha=0.85
    assert abs(sum(out.values()) - 1.0) < 1e-9
    # uniform flow mass -> teleport == ranker probs -> blend is identity
    for m, p in probs.items():
        assert abs(out[m] - p) < 1e-9, (m, out[m])
    # zero flow everywhere -> ranker fallback, no NaN
    out0 = flow_teleport(probs, {"A0": 0.0, "A1": 0.0, "A2": 0.0})
    for m, p in probs.items():
        assert abs(out0[m] - p) < 1e-9 and np.isfinite(out0[m])
    # skewed flow pulls mass toward the high-flow node vs ranker-only
    out1 = flow_teleport(probs, {"A0": 0.0, "A1": 100.0, "A2": 0.0}, alpha=0.85)
    assert out1["A1"] > probs["A1"], out1
