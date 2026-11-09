"""Diagnosis layer tests (alongside detector, silent on clean)."""

import numpy as np
import pandas as pd


def _seg(n=40, shift=None):
    rng = np.random.default_rng(0)
    base = rng.normal(0, 1, size=(n, 2))
    if shift:
        ch, amt = shift
        base[:, ch] += amt
    return pd.DataFrame({"obs_A0": base[:, 0], "obs_A1": base[:, 1]})


def test_attribution_picks_shifted_channel():
    from src.diagnose import attribute_machine, episode_nominal, robust_sigma

    g = _seg()
    nom = episode_nominal(g, ["obs_A0", "obs_A1"])
    sig = robust_sigma(g, ["obs_A0", "obs_A1"])
    seg = _seg(shift=(1, 8.0))
    m, s = attribute_machine(seg, ["obs_A0", "obs_A1"], nom, sig)
    assert m == "A1" and s > 3.0


def test_coordination_single_vs_multi():
    from src.diagnose import classify_coordination, episode_nominal, robust_sigma

    g = _seg()
    cols = ["obs_A0", "obs_A1"]
    nom, sig = episode_nominal(g, cols), robust_sigma(g, cols)
    assert classify_coordination(_seg(shift=(0, 8.0)), cols, nom, sig) == "sensor"
    both = _seg()
    both.iloc[-1, 0] += 8.0
    both.iloc[-1, 1] += 8.0
    assert classify_coordination(both, cols, nom, sig) == "process"


def test_rung_cut():
    from src.diagnose import estimate_rung

    assert estimate_rung(2.0) == "incipient" and estimate_rung(5.0) == "caricature"


def test_diagnose_window_shape():
    from src.diagnose import diagnose_window, episode_nominal, robust_sigma

    g = _seg()
    cols = ["obs_A0", "obs_A1"]
    out = diagnose_window(
        _seg(shift=(0, 8.0)), cols, episode_nominal(g, cols), robust_sigma(g, cols)
    )
    assert set(out) == {"machine", "score_sigma", "coord_class", "rung", "hop_est"}
    assert out["hop_est"] == 0


def _multi_df():
    n = 300
    rng = np.random.default_rng(1)
    d = {
        "episode_id": [1] * n,
        "step": list(range(n)),
        "obs_A0": np.concatenate([rng.normal(0, 1, 160), rng.normal(0, 1, 140) + 6.0]),
        "obs_B0": np.concatenate([rng.normal(0, 1, 200), rng.normal(0, 1, 100) + 6.0]),
        "state_A0": ["RUN"] * 160 + ["DOWN"] * 140,
        "state_B0": ["RUN"] * 200 + ["STARVED"] * 100,
    }
    return pd.DataFrame(d)


def test_multi_origin_orders_by_onset():
    from src.diagnose import diagnose_multi_origin

    g = _multi_df()
    out = diagnose_multi_origin(g, ["obs_A0", "obs_B0"])
    assert [r["machine"] for r in out] == ["A0", "B0"]
    assert out[0]["onset"] <= out[1]["onset"]
    assert out[0]["own_state"] == "DOWN" and out[1]["own_state"] == "STARVED"


def test_counter_onset_finds_delay_step():
    from src.diagnose import machine_onset

    n = 300
    rng = np.random.default_rng(2)
    g = pd.DataFrame(
        {
            "episode_id": [1] * n,
            "step": list(range(n)),
            "obs_C2": rng.normal(0, 1, size=n),
            "state_C2": ["RUN"] * n,
            "tputlag_C2": [0] * 150 + [4] * 150,
            "downrun_C2": [0] * n,
        }
    )
    tick, kind = machine_onset(g, "obs_C2", 0.0, 1.0)
    assert kind == "counter" and abs(tick - 150) <= 4


def test_trigger_gate_drops_pre_trigger_texture():
    from src.diagnose import diagnose_from_trigger

    n = 300
    rng = np.random.default_rng(3)
    a0 = np.concatenate([rng.normal(0, 1, 200), rng.normal(0, 1, 100) + 6.0])
    tex = rng.normal(0, 1, size=n)
    tex[110:115] += 8.0  # pre-trigger texture burst
    g = pd.DataFrame(
        {
            "episode_id": [1] * n,
            "step": list(range(n)),
            "obs_A0": a0,
            "obs_B9": tex,
            "state_A0": ["RUN"] * 200 + ["DOWN"] * 100,
            "state_B9": ["RUN"] * n,
        }
    )
    out = diagnose_from_trigger(g, ["obs_A0", "obs_B9"], trigger=190, back=16)
    machines = [r["machine"] for r in out]
    assert "A0" in machines and "B9" not in machines


def test_first_trigger_picks_first_hot_window():
    import numpy as np

    from src.diagnose import first_trigger

    s = np.array([0.1, 0.5, 0.85, 0.9])
    st = np.array([0, 8, 16, 24])
    assert first_trigger(s, st, 0.8) == 16
    assert first_trigger(s, st, 0.99) is None


def test_confirm_trigger_needs_persistence():
    import numpy as np

    from src.diagnose import confirm_trigger

    s = np.array([0.1, 0.85, 0.1, 0.1])  # isolated spike: unconfirmed
    st = np.array([0, 8, 16, 24])
    assert confirm_trigger(s, st, 0.8, m=2, n=3) is None
    s2 = np.array([0.1, 0.85, 0.86, 0.1])  # 2-of-3: confirmed at 16
    assert confirm_trigger(s2, st, 0.8, m=2, n=3) == 16


def test_abstain_gate_flags_low_confidence():
    import numpy as np

    from src.diagnose import abstain_reason

    assert abstain_reason(np.array([0.5, 0.6]), hi=0.9) == "low-confidence"
    assert abstain_reason(np.array([0.95, 0.5]), hi=0.9) is None


def test_hop_est_uses_twin_topology():
    import pandas as pd

    from src.diagnose import diagnose_from_trigger

    n = 300
    rng = __import__("numpy").random.default_rng(4)
    g = pd.DataFrame(
        {
            "episode_id": [1] * n,
            "step": list(range(n)),
            **{f"obs_M{i}": rng.normal(0, 1, size=n) for i in range(3)},
            "state_M0": ["RUN"] * 200 + ["DOWN"] * 100,
            "state_M1": ["RUN"] * 205 + ["STARVED"] * 95,
            "state_M2": ["RUN"] * 210 + ["STARVED"] * 90,
        }
    )
    g = g.rename(
        columns={
            "obs_M0": "obs_A0",
            "obs_M1": "obs_A1",
            "obs_M2": "obs_A2",
            "state_M0": "state_A0",
            "state_M1": "state_A1",
            "state_M2": "state_A2",
        }
    )
    out = diagnose_from_trigger(g, ["obs_A0", "obs_A1", "obs_A2"], trigger=190, back=64)
    by_m = {r["machine"]: r for r in out}
    assert by_m["A0"]["hop_est"] == 0
    assert by_m["A1"]["hop_est"] == 1
