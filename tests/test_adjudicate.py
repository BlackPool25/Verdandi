"""H-wire adjudication tests (synthetic; real numbers in Task 17 run)."""

from __future__ import annotations

from scripts.adjudicate_h_wires import adjudicate


def test_adjudication_calls_survived_and_falsified():
    rows = adjudicate(
        {"id": "H9", "metric": 0.9, "bar": 0.8, "higher_is_better": True},
        {"id": "H8", "metric": 0.1, "bar": 0.8, "higher_is_better": True},
        battery_id="test",
    )
    assert {r["status"] for r in rows} == {"Survived", "Falsified"}
    assert all(r["battery_id"] == "test" and r["date"] for r in rows)


def test_metrics_row_has_chance_corrected_summaries():
    import numpy as np

    from scripts.adjudicate_h_wires import summarize_metrics

    rng = np.random.default_rng(0)
    y = np.array([0] * 90 + [1] * 10)
    scores = np.concatenate([rng.normal(0, 1, 90), rng.normal(3, 1, 10)])
    dec = (scores > np.median(scores)).astype(int)
    out = summarize_metrics(y, scores, dec)
    assert {"f1", "mcc", "roc_auc", "trivial_f1_all", "n_pos", "n_total"} <= set(out)
    assert out["mcc"] > 0 and out["trivial_f1_all"] < out["f1"]


def test_vus_bar_passes_at_095_and_fails_at_085():
    from scripts.adjudicate_h_wires import adjudicate

    ok = adjudicate({"id": "VUS", "metric": 0.95, "bar": 0.90}, battery_id="t")[0]
    bad = adjudicate({"id": "VUS", "metric": 0.85, "bar": 0.90}, battery_id="t")[0]
    assert ok["status"] == "Survived" and bad["status"] == "Falsified"
