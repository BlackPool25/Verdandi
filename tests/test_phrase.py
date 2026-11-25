"""Task 10 (PRISSUE-71): constrained phrasing fixture tests (TDD RED).

Offline: no network, no Ollama required. The LLM/stylist path is injected
as a fake callable; the Ollama path is flag-gated and disabled by default.
"""

from __future__ import annotations


def _packet():
    return {
        "id": "det-1-160", "root": "B2", "onset": 150, "trigger": 160,
        "verdict": "diagnosed",
        "trace": [
            {"id": "ev-B2", "machine": "B2", "onset": 150,
             "onset_kind": "state", "own_state": "DOWN"},
            {"id": "ev-A1", "machine": "A1", "onset": 152,
             "onset_kind": "state", "own_state": "STARVED"},
        ],
        "paths": [{"id": "path-0", "nodes": ["B2", "A1"], "prob": 0.7}],
        "confidence": {"top1": 0.7},
        "flow": {},
    }


def _decision():
    return {"spec": "v1", "packet_id": "det-1-160", "machine": "B2",
            "machine_prob": 0.8, "fault_family": "drift", "family_prob": 0.75,
            "severity": "SEV3", "severity_prob": 0.9, "verdict": "decided"}


def _good_candidate():
    # Rephrased prose only; numbers/IDs copied verbatim from fixtures.
    return {
        "title": "B2 root cause at tick 150",
        "summary": ["B2 went DOWN at tick 150"],
        "findings": [
            {"claim": "B2 origin with probability 0.8", "evidence_ids": ["ev-B2"]},
            {"claim": "A1 starved after onset 152", "evidence_ids": ["ev-A1"]},
            {"claim": "causal path confidence 0.7", "evidence_ids": ["path-0"]},
        ],
        "actions": ["inspect root machine B2"],
    }


def test_schema_valid_candidate_passes_verifier():
    from src.phrase import extract_facts, verify

    facts = extract_facts(_packet(), _decision())
    ok, reason = verify(_good_candidate(), facts)
    assert ok, reason


def test_citations_subset_of_packet_ids():
    from src.phrase import extract_facts, verify

    facts = extract_facts(_packet(), _decision())
    assert set(facts["ids"]) >= {"det-1-160", "ev-B2", "ev-A1", "path-0"}
    ok, _ = verify(_good_candidate(), facts)
    assert ok
    bad = dict(_good_candidate(), findings=[
        {"claim": "B2 origin", "evidence_ids": ["ev-NOBODY"]}])
    ok, reason = verify(bad, facts)
    assert not ok and "citation" in reason


def test_numbers_diff_exact():
    from src.phrase import extract_facts, verify

    facts = extract_facts(_packet(), _decision())
    ok, _ = verify(_good_candidate(), facts)
    assert ok
    invented = dict(_good_candidate(), findings=[
        {"claim": "B2 origin with probability 0.99", "evidence_ids": ["ev-B2"]}])
    ok, reason = verify(invented, facts)
    assert not ok and "number" in reason


def test_invented_number_falls_back_to_template():
    from src.phrase import phrase

    def bad_stylist(facts):
        return {"title": "B2", "summary": ["prob 0.99 invented"],
                "findings": [{"claim": "0.99", "evidence_ids": ["ev-B2"]}],
                "actions": ["x"]}

    out = phrase(_packet(), _decision(), stylist=bad_stylist, allow_llm=True)
    assert out["path"] == "template"
    assert "0.99" not in out["text"]


def test_unresolvable_citation_falls_back_to_template():
    from src.phrase import phrase

    def bad_stylist(facts):
        return {"title": "B2", "summary": ["ok"],
                "findings": [{"claim": "ok", "evidence_ids": ["ev-GHOST"]}],
                "actions": ["x"]}

    out = phrase(_packet(), _decision(), stylist=bad_stylist, allow_llm=True)
    assert out["path"] == "template"
    assert "ev-GHOST" not in out["text"]


def test_template_only_by_default_no_stylist_call():
    from src.phrase import phrase

    def exploding_stylist(facts):  # pragma: no cover
        raise AssertionError("network must not be touched on default path")

    out = phrase(_packet(), _decision(), stylist=exploding_stylist)
    assert out["path"] == "template"
    assert out["attempts"] == 0


def test_single_retry_then_template_verbatim():
    from src.phrase import phrase, template_text

    calls = []

    def always_bad(facts):
        calls.append(1)
        return {"title": "B2", "summary": ["invented 0.99"],
                "findings": [{"claim": "0.99", "evidence_ids": ["ev-B2"]}],
                "actions": ["x"]}

    out = phrase(_packet(), _decision(), stylist=always_bad, allow_llm=True)
    assert out["path"] == "template"
    assert len(calls) == 2  # initial + exactly one retry
    expected = template_text(_packet(), _decision())
    assert out["text"] == expected


def test_retry_success_ships_rephrased():
    from src.phrase import phrase

    calls = []

    def flaky(facts):
        calls.append(1)
        if len(calls) == 1:
            return {"no": "schema"}
        return _good_candidate()

    out = phrase(_packet(), _decision(), stylist=flaky, allow_llm=True)
    assert out["path"] == "llm"
    assert len(calls) == 2


def test_ollama_path_disabled_by_default():
    from src.phrase import phrase_with_ollama

    out = phrase_with_ollama(_packet(), _decision())
    assert out["path"] == "template"
    assert "disabled" in out.get("reason", "")
