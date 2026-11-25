"""Task 4 (62): eval_tev kill-bar contract. Offline — no Ollama calls."""
import importlib.util
import pathlib
import re

import pytest


def _load():
    path = pathlib.Path(__file__).resolve().parent.parent / "scripts" / "eval_tev.py"
    spec = importlib.util.spec_from_file_location("eval_tev_task4", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod, path.read_text()


def test_default_n60_pinned_seed():
    import inspect

    mod, _ = _load()
    sig = inspect.signature(mod.main)
    assert sig.parameters["n_eps"].default == 60
    assert sig.parameters["seed"].default == 0


def test_eval_uses_short_explicit_timeout():
    mod, src = _load()
    m = re.search(r"TevClient\(timeout=(\w+)", src)
    assert m, "eval must construct TevClient with an explicit short timeout"
    val = getattr(mod, m.group(1), None)
    val = int(val) if val is not None else int(m.group(1))
    assert val < 300, f"eval timeout {val} must be well under the 300s class default"


def test_class_default_timeout_untouched():
    from src import jev

    import inspect as _i

    assert _i.signature(jev.TevClient.__init__).parameters["timeout"].default == 300


def test_kill_verdict_boundaries():
    mod, _ = _load()
    assert mod.kill_verdict(0.20) == "KILL"
    assert mod.kill_verdict(0.299) == "KILL"
    assert mod.kill_verdict(0.671) == "WIN"
    assert mod.kill_verdict(0.80) == "WIN"
    assert mod.kill_verdict(0.45) == "HOLD"


def test_machine_sc_vote_majority():
    mod, _ = _load()

    class FakeClient:
        def __init__(self, seq):
            self.seq = seq

        def ask(self, pkt, questions):
            return {"machine": {"choice": self.seq.pop(0), "probability": 1.0}}

    q = {"machine": {"type": "choice", "instructions": "m", "criteria": {"A": "x", "B": "y"}}}
    assert mod.machine_sc_vote(FakeClient(["A", "B", "A", "A", "B"]), {}, q, n=5) == "A"
    assert mod.machine_sc_vote(FakeClient([None, None, "B", None, "B"]), {}, q, n=5) == "B"
    assert mod.machine_sc_vote(FakeClient([None] * 5), {}, q, n=5) is None


def test_kill_bar_outputs_present():
    _, src = _load()
    for token in ("0.671", "null", "self-consistency"):
        assert token in src, f"eval must report kill-bar token: {token}"


def test_parse_decision_output():
    mod, _ = _load()
    assert mod.parse_decision_output("M1 72%", ["M1", "M2"]) == ("M1", 0.72)
    assert mod.parse_decision_output("B7P", ["B7P", "C6"]) == ("B7P", 1.0)
    assert mod.parse_decision_output("no decision here", ["M1", "M2"]) == (None, 0.0)
    assert mod.parse_decision_output("", ["M1"]) == (None, 0.0)


def test_cli_client_shape_and_timeout():
    mod, _ = _load()
    assert mod.CliDecisionClient(timeout=60).timeout < 300
    seen = {}

    def fake_run(argv, input, capture_output, timeout):
        seen["argv"] = argv
        seen["input"] = input
        seen["timeout"] = timeout

        class R:
            returncode = 0
            stdout = b"M2 61%\n"

        return R()

    c = mod.CliDecisionClient(runner=fake_run)
    out = c.ask({"id": "d", "trace": []},
                {"machine": {"type": "choice", "instructions": "Which machine?",
                             "criteria": {"M1": "first DOWN", "M2": "second STARVED"}}})
    assert out == {"machine": {"choice": "M2", "probability": 0.61}}
    assert "--ask" in seen["argv"] and "tev1:4b" in seen["argv"]
    assert any(a.startswith("M1=") for a in seen["argv"])
    assert seen["timeout"] < 300


def test_shuffle_mode_params():
    import inspect

    mod, _ = _load()
    sig = inspect.signature(mod.main)
    assert sig.parameters["order"].default == "fixed"
    assert sig.parameters["order_seed"].default == 0


def test_shuffle_criteria_deterministic():
    mod, _ = _load()
    import numpy as np

    crit = {m: f"desc {m}" for m in ["A", "B", "C", "D", "E"]}
    r1 = mod.shuffled_criteria(crit, np.random.default_rng(1))
    r2 = mod.shuffled_criteria(crit, np.random.default_rng(1))
    assert list(r1) == list(r2)
    assert sorted(r1) == sorted(crit)


def test_shuffle_changes_order_for_some_seed():
    mod, _ = _load()
    import numpy as np

    crit = {m: f"desc {m}" for m in ["A", "B", "C", "D", "E"]}
    diffs = [s for s in range(10)
             if list(mod.shuffled_criteria(crit, np.random.default_rng(s))) != list(crit)]
    assert diffs, "shuffle must permute order for at least one seed in 0..9"


def test_apply_order_fixed_preserves_insertion():
    mod, _ = _load()
    import numpy as np

    qs = {"machine": {"type": "choice", "instructions": "m",
                      "criteria": {"B": "x", "A": "y", "C": "z"}}}
    out = mod.apply_order(qs, "fixed", np.random.default_rng(0))
    assert list(out["machine"]["criteria"]) == ["B", "A", "C"]


def test_apply_order_shuffled_deterministic_and_complete():
    mod, _ = _load()
    import numpy as np

    qs = {"machine": {"type": "choice", "instructions": "m",
                      "criteria": {m: f"d {m}" for m in ["A", "B", "C", "D", "E"]}},
          "fault_family": {"type": "choice", "instructions": "f",
                           "criteria": {f: f"d {f}" for f in
                                        ["breakdown", "delay", "loss", "quality"]}}}
    a = mod.apply_order(qs, "shuffled", np.random.default_rng(3))
    b = mod.apply_order(qs, "shuffled", np.random.default_rng(3))
    assert list(a["machine"]["criteria"]) == list(b["machine"]["criteria"])
    assert sorted(a["machine"]["criteria"]) == ["A", "B", "C", "D", "E"]
    assert sorted(a["fault_family"]["criteria"]) == ["breakdown", "delay", "loss", "quality"]


def test_eval_stays_phrasing_only_no_ranker_import():
    _, src = _load()
    for token in ("eval_stacked", "LambdaRank", "stage2-oof", "from src.rank"):
        assert token not in src, f"tev eval must not pipe into ranker: {token}"


def test_order_cli_flags_present():
    _, src = _load()
    assert "--order" in src and "--order-seed" in src and "shuffled" in src


def test_sample_episodes_deterministic_and_pinned(tmp_path):
    import pandas as pd

    mod, _ = _load()
    for i in range(3):
        pd.DataFrame({"episode_id": [i] * 4, "step": range(4),
                      "obs_X": 1.0}).to_parquet(tmp_path / f"s{i}.parquet")
    paths = sorted(str(p) for p in tmp_path.glob("*.parquet"))
    assert list(mod.sample_episodes(paths, 2, seed=0)) == list(mod.sample_episodes(paths, 2, seed=0))
    assert len(mod.sample_episodes(paths, 2, seed=0)) == 2


def test_load_episodes_returns_only_sampled(tmp_path):
    import pandas as pd

    mod, _ = _load()
    for i in range(3):
        pd.DataFrame({"episode_id": [i] * 4, "step": range(4),
                      "obs_X": 1.0}).to_parquet(tmp_path / f"s{i}.parquet")
    paths = sorted(str(p) for p in tmp_path.glob("*.parquet"))
    eps = mod.sample_episodes(paths, 2, seed=0)
    df = mod.load_episodes(paths, eps)
    assert sorted(df["episode_id"].unique()) == sorted(eps)
    assert len(df) == 8
