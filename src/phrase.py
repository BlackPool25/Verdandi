"""Constrained phrasing (PRISSUE-71): two-stage extractor + stylist + verifier.

Stage 1 (extractor) copies numbers/evidence IDs verbatim from the packet,
decision, and template card/dossier — the LLM never computes or copies
numbers itself. Stage 2 (stylist) rewrites prose only. The verifier diffs
every digit-run in the candidate against the input and checks every
citation resolves to a packet ID. Any failure (schema-invalid, invented
number, unresolvable citation, stylist error) triggers exactly one retry,
then falls back to the template rendered verbatim.

Default path is template-only (no network). The Ollama path is opt-in
behind VERDANDI_PHRASE_LLM=1 and uses an OPEN schema (no
additionalProperties:false — legacy GBNF closed-schema cost is 12-24%/token;
see research-tev phrasing section). p95 gate: disable the Ollama path if
measured p95 > 8s.
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.request

from src.reporter import build_card, build_dossier

_NUM_RE = re.compile(r"\d+(?:\.\d+)?")

_OLLAMA_FLAG = "VERDANDI_PHRASE_LLM"
_P95_BUDGET_S = 8.0


def _numbers_of(obj: object) -> set[str]:
    return set(_NUM_RE.findall(json.dumps(obj, sort_keys=True, default=str)))


def _packet_ids(packet: dict) -> set[str]:
    out = {packet.get("id")}
    out |= {t.get("id") for t in packet.get("trace", [])}
    out |= {p.get("id") for p in packet.get("paths", [])}
    return {i for i in out if i}


def extract_facts(packet: dict, decision: dict) -> dict:
    """Copy numbers/IDs verbatim; render the template baseline."""
    card = build_card(packet, decision)
    dossier = build_dossier(packet, decision)
    blob = {"packet": packet, "decision": decision,
            "card": card, "dossier": dossier}
    return {
        "numbers": sorted(_numbers_of(blob)),
        "ids": sorted(_packet_ids(packet)),
        "template": render_template(card, dossier),
        "card": card,
        "dossier": dossier,
    }


def render_template(card: dict, dossier: dict) -> str:
    lines = [
        f"verdict: {card.get('verdict')}",
        f"root: {card.get('root')}",
        f"severity: {card.get('severity')}",
        f"packet: {card.get('packet_id')}",
    ]
    for claim in card.get("claims", []):
        lines.append(
            f"- {claim.get('text')}: {claim.get('value')} "
            f"[{claim.get('evidence_id')}]")
    return "\n".join(lines)


def template_text(packet: dict, decision: dict) -> str:
    facts = extract_facts(packet, decision)
    return facts["template"]


def verify(candidate: object, facts: dict) -> tuple[bool, str]:
    """Open-schema check: required keys/types only; extras ignored."""
    if not isinstance(candidate, dict):
        return False, "schema-invalid: candidate must be an object"
    for key in ("title", "summary", "findings", "actions"):
        if key not in candidate:
            return False, f"schema-invalid: missing {key}"
    if not isinstance(candidate["title"], str):
        return False, "schema-invalid: title must be a string"
    if not (isinstance(candidate["summary"], list)
            and all(isinstance(s, str) for s in candidate["summary"])):
        return False, "schema-invalid: summary must be string[]"
    if not (isinstance(candidate["actions"], list)
            and all(isinstance(s, str) for s in candidate["actions"])):
        return False, "schema-invalid: actions must be string[]"
    findings = candidate["findings"]
    if not isinstance(findings, list):
        return False, "schema-invalid: findings must be an array"
    for f in findings:
        if (not isinstance(f, dict) or not isinstance(f.get("claim"), str)
                or not isinstance(f.get("evidence_ids"), list)
                or not all(isinstance(e, str) for e in f["evidence_ids"])):
            return False, "schema-invalid: finding needs claim + evidence_ids[]"
    valid = set(facts["ids"])
    for f in findings:
        for eid in f["evidence_ids"]:
            if eid not in valid:
                return False, f"citation-unresolvable: {eid}"
    allowed = set(facts["numbers"])
    scrubbed = {k: v for k, v in candidate.items() if k != "_latency_s"}
    for run in _numbers_of(scrubbed):
        if run not in allowed:
            return False, f"number-mismatch: {run} not in input"
    return True, "ok"


def render_candidate(candidate: dict) -> str:
    lines = [candidate["title"]]
    lines.extend(f"- {s}" for s in candidate["summary"])
    for f in candidate["findings"]:
        lines.append(f"- {f['claim']} [{', '.join(f['evidence_ids'])}]")
    lines.append("actions: " + "; ".join(candidate["actions"]))
    return "\n".join(lines)


def phrase(packet: dict, decision: dict, stylist=None,
           allow_llm: bool = False) -> dict:
    """Phrase a card/dossier. Template-only unless allow_llm + stylist."""
    template = template_text(packet, decision)
    if not allow_llm or stylist is None:
        return {"text": template, "path": "template", "attempts": 0,
                "reason": "template-default"}
    facts = extract_facts(packet, decision)
    reason = ""
    attempts = 0
    candidate = None
    for _ in range(2):  # initial + single retry
        attempts += 1
        try:
            candidate = stylist(facts)
        except Exception as exc:  # noqa: BLE001 - any stylist error falls back
            reason = f"stylist-error: {exc}"
            continue
        ok, reason = verify(candidate, facts)
        if ok:
            return {"text": render_candidate(candidate), "path": "llm",
                    "attempts": attempts, "candidate": candidate}
    return {"text": template, "path": "template", "attempts": attempts,
            "reason": reason}


def phrase_with_ollama(packet: dict, decision: dict,
                       model: str = "tev1:4b",
                       base_url: str = "http://localhost:11434",
                       timeout: float = _P95_BUDGET_S) -> dict:
    """Ollama stylist path. Disabled unless VERDANDI_PHRASE_LLM=1.

    Uses an open schema (no additionalProperties:false) and temp 0;
    every response passes through verify() with the same single-retry
    + template-verbatim fallback as phrase().
    """
    template = template_text(packet, decision)
    if os.environ.get(_OLLAMA_FLAG) != "1":
        return {"text": template, "path": "template", "attempts": 0,
                "reason": "llm-disabled (set VERDANDI_PHRASE_LLM=1 to enable)"}

    timing: dict = {}

    def _stylist(facts: dict) -> dict:
        schema_hint = (
            '{"title": str, "summary": [str], '
            '"findings": [{"claim": str, "evidence_ids": [str]}], '
            '"actions": [str]} — open schema, extra keys allowed')
        prompt = (
            "Rephrase the incident prose below. Rules: copy every number "
            "and evidence ID verbatim from the input; never invent numbers "
            "or IDs; never add claims. Reply with JSON only matching "
            f"{schema_hint}.\nINPUT:\n{facts['template']}")
        body = json.dumps({"model": model, "prompt": prompt,
                           "stream": False,
                           "options": {"temperature": 0}}).encode()
        t0 = time.monotonic()
        req = urllib.request.Request(
            f"{base_url}/api/generate", data=body,
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = json.loads(resp.read().decode())["response"]
        latency = time.monotonic() - t0
        parsed = json.loads(raw[raw.index("{"):raw.rindex("}") + 1])
        # Kept OUT of the verified dict: latency digits would always fail
        # the digit-run diff (verify also defensively ignores _latency_s).
        timing["latency_s"] = latency
        return parsed

    out = phrase(packet, decision, stylist=_stylist, allow_llm=True)
    if "latency_s" in timing:
        out["latency_s"] = timing["latency_s"]
    candidate = out.get("candidate") or {}
    if "_latency_s" in candidate:
        out["latency_s"] = candidate["_latency_s"]
    return out


def p95_gate(latencies: list[float],
             budget: float = _P95_BUDGET_S) -> tuple[bool, float]:
    """Return (enabled, p95). Disable the Ollama path when p95 > budget."""
    if not latencies:
        return True, 0.0
    ordered = sorted(latencies)
    p95 = ordered[max(0, min(len(ordered) - 1,
                             int(0.95 * len(ordered))))]
    return p95 <= budget, p95
