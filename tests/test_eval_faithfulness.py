"""Task 6 (PRISSUE-72): citation recall + NLI entailment scaffolding (TDD RED).

Stub clients only — CI never downloads a model. Real-model arm (if any) is
gated on VERDANDI_MNLI_PATH and skipped with reason otherwise.
"""

import os

import pytest


def _packet():
    return {
        "id": "det-1-160", "root": "B2", "onset": 150, "trigger": 160,
        "verdict": "diagnosed",
        "trace": [
            {"id": "ev-B2", "machine": "B2", "onset": 150, "onset_kind": "state", "own_state": "DOWN"},
            {"id": "ev-A1", "machine": "A1", "onset": 152, "onset_kind": "state", "own_state": "STARVED"},
        ],
        "paths": [{"id": "path-0", "nodes": ["B2", "A1"], "prob": 0.7}],
        "confidence": {"top1": 0.7},
        "flow": {},
    }


def _decision():
    return {"spec": "v1", "packet_id": "det-1-160", "machine": "B2",
            "machine_prob": 0.8, "fault_family": "drift", "family_prob": 0.75,
            "severity": "SEV3", "severity_prob": 0.9, "verdict": "decided"}


class _EntailStub:
    """Stub NLI client: entailment iff hypothesis names the cited machine."""

    def entails(self, premise, hypothesis):
        if "B2" in premise and "B2" in hypothesis:
            return {"label": "entailment", "prob": 0.92}
        return {"label": "contradiction", "prob": 0.85}


class _FlipStub:
    """Stub that flips by order: fwd entails, rev contradicts."""

    def entails(self, premise, hypothesis, order="fwd"):
        if order == "fwd":
            return {"label": "entailment", "prob": 0.9}
        return {"label": "contradiction", "prob": 0.9}


def test_slot_recall_template_is_one():
    from src.faithfulness import coverage_recall, precision_card, slot_recall
    from src.reporter import build_card

    card = build_card(_packet(), _decision())
    assert slot_recall(card, _packet()) == 1.0
    assert precision_card(card, _packet()) == 1.0
    assert coverage_recall(card, _packet()) == pytest.approx(0.5)


def test_abstain_excluded():
    from src.faithfulness import aggregate
    from src.reporter import build_card

    pkt, dec = _packet(), _decision()
    good = build_card(pkt, dec)
    abst = build_card(pkt, dict(dec, verdict="abstain", machine=None))
    assert abst["claims"] == []
    m = aggregate([(good, pkt), (abst, pkt)])
    assert m["n_abstain"] == 1 and m["n"] == 1
    assert m["recall_slot"] == 1.0


def test_empty_diag_packet():
    from src.faithfulness import aggregate, coverage_recall, slot_recall
    from src.packet import emit_packet
    from src.reporter import build_card

    pkt = emit_packet([], trigger=160, sensor_verdict="unknown",
                      fault_family=None, ep=1)
    assert pkt["verdict"] == "abstain"
    card = build_card(pkt, {"verdict": "abstain", "machine": None})
    assert card["verdict"] == "abstain" and card["claims"] == []
    # No crash on empty trace/paths; abstains excluded downstream.
    m = aggregate([(card, pkt)])
    assert m["n"] == 0 and m["n_abstain"] == 1
    assert slot_recall(card, pkt) is None
    assert coverage_recall(card, pkt) is None


def test_nli_stub_entails():
    from src.faithfulness import judge_claim
    from src.reporter import build_card

    card = build_card(_packet(), _decision())
    origin = next(c for c in card["claims"] if c["text"] == "origin")
    r = judge_claim(_packet(), origin, client=_EntailStub())
    assert r["label"] == "entailment" and r["entailed"] is True


def test_nli_stub_contradicts_swapped_machine():
    from src.faithfulness import judge_claim

    bad = {"text": "origin", "value": "ZZ9", "evidence_id": "ev-B2"}
    r = judge_claim(_packet(), bad, client=_EntailStub())
    assert r["label"] == "contradiction" and r["entailed"] is False


def test_nli_empty_premise_non_entailment():
    from src.faithfulness import judge_claim

    orphan = {"text": "origin", "value": "B2", "evidence_id": "ev-NOHIT"}
    r = judge_claim(_packet(), orphan, client=_EntailStub())
    assert r["entailed"] is False  # recall=1 requires non-empty cited set


def test_swap_disagreement_drops_judge():
    from src.faithfulness import aggregate
    from src.reporter import build_card

    pkt, dec = _packet(), _decision()
    card = build_card(pkt, dec)
    m = aggregate([(card, pkt)], client=_FlipStub())
    assert m["nli"]["swap_agree"] is False
    assert m["nli"]["label"] == "unjudged"
    # Kill-criterion path: deterministic P/R still returned.
    assert m["recall_slot"] == 1.0


def test_no_client_skips_with_reason():
    from src.faithfulness import NliUnavailable, corpus_nli, nli_entails

    with pytest.raises(NliUnavailable):
        nli_entails("premise", "hypothesis", client=None)
    r = corpus_nli([], client=None)
    assert r["status"] == "SKIPPED (no local MNLI model)"


@pytest.mark.skipif(
    not os.environ.get("VERDANDI_MNLI_PATH"),
    reason="no local MNLI model; stub path covered",
)
def test_real_model_gated():
    from src.faithfulness import corpus_nli

    path = os.environ["VERDANDI_MNLI_PATH"]
    assert os.path.exists(path)
    corpus_nli([], client=path)


# --- Fix loop round 1 (task-6-review.md findings F1-F3) ---


def test_local_mnli_client_honors_order():
    """F2: rev must swap premise/hypothesis positions (order-bias test).

    A client whose rev-runs duplicate fwd-runs makes swap_agree vacuously
    True and flip_rate always 0 — the gate would be dead where it matters.
    """
    from src.faithfulness import LocalMnliClient

    seen = []

    def fake_encode(premise, hypothesis):
        seen.append((premise, hypothesis))
        return {"label": "entailment", "prob": 0.9}

    client = LocalMnliClient(fake_encode)
    client.entails("PREMISE", "HYPOTHESIS", order="fwd")
    client.entails("PREMISE", "HYPOTHESIS", order="rev")
    assert seen[0] == ("PREMISE", "HYPOTHESIS")
    assert seen[1] == ("HYPOTHESIS", "PREMISE"), (
        f"rev must swap positions, got {seen[1]}"
    )


def test_nli_swap_gate_fires_through_local_client():
    """F2 end-to-end: order-sensitive encode flip → unjudged claim."""
    from src.faithfulness import LocalMnliClient, nli_entails

    def order_biased(premise, hypothesis):
        # Entails only in fwd position order; contradicts when swapped.
        if premise.startswith("Machine"):
            return {"label": "entailment", "prob": 0.9}
        return {"label": "contradiction", "prob": 0.9}

    r = nli_entails("Machine B2 DOWN at tick 150 (state).",
                    "The fault originated at B2.",
                    client=LocalMnliClient(order_biased))
    assert r["swap_agree"] is False and r["label"] == "unjudged"


def test_eval_nli_requirements_parse():
    """F3: every entry must be valid pip requirements syntax (no inline flags)."""
    import re

    with open("requirements-eval-nli.txt") as f:
        lines = f.read().splitlines()
    assert any(l.strip() and not l.strip().startswith("#") for l in lines)
    for raw in lines:
        ln = raw.strip()
        if not ln or ln.startswith("#"):
            continue
        if ln.startswith("-"):
            continue  # pip option line (--index-url / --extra-index-url)
        assert "--" not in ln and "://" not in ln, (
            f"invalid requirements entry: {ln!r}"
        )
        assert re.match(r"^[A-Za-z0-9_.\-\[\]]", ln), (
            f"invalid requirements entry: {ln!r}"
        )


def test_fmt_rate_undefined_on_empty_denominator():
    """F1: zero-denominator rates print as undefined, never 0.000."""
    from src.faithfulness import fmt_rate

    assert fmt_rate(0, 0) == "undefined (0 non-abstain)"
    assert fmt_rate(3, 4) == "0.750"
    assert fmt_rate(0, 5) == "0.000"
