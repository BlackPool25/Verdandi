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
