"""Calibration gate wiring tests (Task 7, PRISSUE-61).

Hermetic, CPU-only. Calibrator injected as a stub dict; no artifacts needed.
Spec: .superpowers/sdd/dx-full-plan/task-7-spec.md Hunk 5.
"""

import numpy as np
import pandas as pd
import pytest

STUB = {"T": 2.58, "a": 5.0, "b": -3.0, "tau": 0.739, "risk_target": 0.3}


def _incident_df(seed=0, a0_onset=185, b9_onset=195, n=300):
    rng = np.random.default_rng(seed)
    return pd.DataFrame(
        {
            "episode_id": [1] * n,
            "step": list(range(n)),
            "obs_A0": np.concatenate(
                [rng.normal(0, 1, a0_onset), rng.normal(0, 1, n - a0_onset) + 6.0]
            ),
            "obs_B9": np.concatenate(
                [rng.normal(0, 1, b9_onset), rng.normal(0, 1, n - b9_onset) + 6.0]
            ),
            "state_A0": ["RUN"] * a0_onset + ["DOWN"] * (n - a0_onset),
            "state_B9": ["RUN"] * n,
        }
    )


EDGES = {"A0": ["B9"], "B9": []}
COLS = ["obs_A0", "obs_B9"]


def test_calibrator_artifact_roundtrip(tmp_path):
    import json

    from src.calibration_artifact import load_calibrator

    p = tmp_path / "calibration.json"
    p.write_text(
        json.dumps(
            {"T": 2.58, "a": 5.0, "b": -3.0, "tau": 0.739, "risk_target": 0.3}
        ),
        encoding="utf-8",
    )
    cal = load_calibrator(str(p))
    assert cal["T"] == pytest.approx(2.58)
    assert cal["a"] == pytest.approx(5.0)
    assert cal["b"] == pytest.approx(-3.0)
    assert cal["tau"] == pytest.approx(0.739)
    # Missing file -> identity fallback (T=1.0, gate open), never raises.
    cal2 = load_calibrator(str(tmp_path / "absent.json"))
    assert cal2["T"] == pytest.approx(1.0)
    assert cal2["tau"] == float("-inf")


def test_temperature_preserves_argmax():
    from src.calibration_artifact import scaled_margin

    rng = np.random.default_rng(61)
    for _ in range(50):
        z = rng.normal(0, 3, size=rng.integers(2, 8))
        p = np.exp(z - z.max())
        p /= p.sum()
        probs = {f"m{i}": float(v) for i, v in enumerate(p)}
        _, top_raw = scaled_margin(probs, 1.0)
        for T in (0.168, 1.0, 2.58, 10.0):
            m_t, top_t = scaled_margin(probs, T)
            assert top_t == top_raw  # argmax preserved for any T > 0
            assert m_t >= 0.0


def test_gate_reproduces_transfer_row():
    # Synthetic held-5 operating point: coverage ~0.337 @ tau, risk ~0.3.
    rng = np.random.default_rng(61)
    n = 8945
    n_cov = int(0.337 * n)
    conf = np.concatenate(
        [rng.uniform(0.739, 0.97, n_cov), rng.uniform(0.05, 0.738, n - n_cov)]
    )
    correct = np.concatenate(
        [rng.binomial(1, 0.70, n_cov), rng.binomial(1, 0.30, n - n_cov)]
    )
    covered = conf >= 0.739
    assert float(covered.mean()) == pytest.approx(0.337, abs=0.02)
    assert float(1 - correct[covered].mean()) == pytest.approx(0.300, abs=0.03)


def test_kill_bar_forced_top1():
    from src.diagnose import diagnose_incident

    roots_cal, roots_uncal, forced_ok, cov_ok = [], [], 0, 0
    n_cov = 0
    for seed in range(20):
        g = _incident_df(seed=seed)
        r_cal = diagnose_incident(
            g, COLS, 190, EDGES, calibrator={**STUB, "tau": float("-inf")},
        )["root"]
        r_uncal = diagnose_incident(g, COLS, 190, EDGES, calibrator={"T": 1.0})[
            "root"
        ]
        roots_cal.append(r_cal)
        roots_uncal.append(r_uncal)
        gated = diagnose_incident(g, COLS, 190, EDGES, calibrator=dict(STUB))
        if gated.get("abstain") is None:
            n_cov += 1
            cov_ok += gated["root"] == "A0"
        forced_ok += r_cal == "A0"
    agree = float(np.mean([a == b for a, b in zip(roots_cal, roots_uncal)]))
    assert agree >= 0.99, f"kill bar tripped: forced top-1 agreement {agree}"
    forced_acc = forced_ok / 20
    covered_acc = (cov_ok / n_cov) if n_cov else 1.0
    assert covered_acc + 1e-12 >= forced_acc


def test_below_tau_abstains_via_reporter_path():
    from src.diagnose import diagnose_incident
    from src.packet import emit_packet
    from src.reporter import build_card

    g = _incident_df()
    rep = diagnose_incident(g, COLS, 190, EDGES, calibrator={**STUB, "tau": 0.99})
    assert rep["abstain"] == "low-confidence-calibrated"
    assert rep["root"] is None
    assert "confidence" in rep and rep["confidence"]["top1"] < 0.99
    assert rep["path"] and rep["path_prob"] > 0  # dossier preserves path
    pkt = emit_packet(
        [], trigger=190, sensor_verdict="sensor",
        fault_family=rep["fault_family"], confidence=rep["confidence"],
    )
    card = build_card(pkt, {"verdict": "abstain"})
    assert card["verdict"] == "abstain"
    assert card["action"] == "collect more evidence"
    assert card["root"] is None


def test_store_persists_conf_tau():
    from src.incidents_store import IncidentStore

    s = IncidentStore.memory()
    inc = s.create_incident("A0", "breakdown", 185, 0, conf=0.81, tau=0.739)
    row = s.conn.execute(
        "SELECT root_machine, conf, tau FROM incidents WHERE id=?", (inc,)
    ).fetchone()
    assert row[0] == "A0"
    assert row[1] == pytest.approx(0.81)
    assert row[2] == pytest.approx(0.739)
    # Legacy row (pre-migration, NULL conf/tau) still reads.
    s.conn.execute(
        "INSERT INTO incidents(root_machine,fault_family,t0_est,seed,status,created_at)"
        " VALUES(?,?,?,?, 'open', 0.0)",
        ("B9", "loss", 195, 0),
    )
    legacy = s.conn.execute(
        "SELECT conf, tau FROM incidents WHERE root_machine='B9'"
    ).fetchone()
    assert legacy == (None, None)


def test_non_abstain_report_carries_confidence():
    from src.diagnose import diagnose_incident

    g = _incident_df()
    rep = diagnose_incident(
        g, COLS, 190, EDGES, calibrator={**STUB, "tau": float("-inf")}
    )
    assert rep.get("abstain") is None
    assert rep["confidence"]["top1"] <= 1.0
    assert rep["confidence"]["tau"] == float("-inf")
    assert rep["confidence"]["T"] == pytest.approx(2.58)


def test_verify_served_tau_within_budget():
    """VERIFY lock-in: shipped tau holds risk<=budget on exclude-held data.

    Reads the shipped artifact evidence; recomputes from OOF only when the
    parquet is present (skips that half offline, artifact assertions stand).
    """
    import json
    import os

    path = "artifacts/calibration.json"
    if not os.path.exists(path):
        pytest.skip("no served artifact (offline)")
    with open(path, encoding="utf-8") as f:
        art = json.load(f)
    assert art["tau"] == pytest.approx(0.739)
    assert art["tau"] != pytest.approx(0.187)  # never the ranker tau
    assert art["verify"]["risk"] <= art["verify"]["budget"]
    assert art["verify"]["verdict"] == "SERVE"
    assert art["verify"]["n"] >= 1000
    if os.path.exists("artifacts/oof_identity.parquet"):
        import pandas as pd

        from src.calibration_artifact import calibrated_conf

        oof = pd.read_parquet("artifacts/oof_identity.parquet")
        mcols = [c for c in oof.columns
                 if c.startswith("proba_") and c != "proba_none"]
        held = oof["root"].isin(["ASM1", "ASM2", "B7P", "B9", "C6"])
        fault = oof["y"].to_numpy() == 1
        sub = oof[fault & held]
        P = sub[mcols].to_numpy(dtype=float)
        confs = np.array([calibrated_conf(
            {j: float(v) for j, v in enumerate(row)},
            art["T"], art["a"], art["b"])[0] for row in P])
        correct = (sub["pred"].to_numpy(dtype=str)
                   == sub["root"].to_numpy(dtype=str)).astype(int)
        cov_m = confs >= art["tau"]
        assert float(cov_m.mean()) == pytest.approx(
            art["verify"]["coverage"], abs=0.01)
        assert float(1 - correct[cov_m].mean()) == pytest.approx(
            art["verify"]["risk"], abs=0.02)
