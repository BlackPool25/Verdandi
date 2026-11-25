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
