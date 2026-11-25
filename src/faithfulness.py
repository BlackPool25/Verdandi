"""Citation recall + local-NLI entailment scaffolding (PRISSUE-72).

Three recall layers (spec task-6-spec.md sec 2):
 1. slot_recall      — deterministic regression gate (required claim slots
                      present and every evidence_id in packet IDs).
 2. coverage_recall  — diagnostic trace-coverage (fraction of ev-* IDs cited).
 3. ALCE/NLI recall  — per-claim entailment via injectable client; needs a
                      local MNLI model. client=None -> NliUnavailable; the
                      eval catches it and skips honestly. CI never downloads.

Judge reliability rule (sec 4): 3 runs x 2 orders, majority vote, swap must
agree; flip rate >20% drops the judge arm (kill criterion), deterministic
P/R still returned. Single-run verdicts never gate.
"""

from __future__ import annotations

import inspect
import os
from collections import Counter

REQUIRED_SLOTS = ("origin", "onset", "causal path")

NLI_SKIP_REASON = "no local MNLI model"

FLIP_KILL_RATE = 0.20
NLI_RUNS = 3


class NliUnavailable(RuntimeError):
    """Raised when no NLI client/model is configured (offline skip)."""


def _ids(packet: dict) -> set[str]:
    out = {packet.get("id")}
    out |= {t.get("id") for t in packet.get("trace", [])}
    out |= {p.get("id") for p in packet.get("paths", [])}
    return {i for i in out if i}


def _is_abstain(card: dict) -> bool:
    return card.get("verdict") == "abstain" or not card.get("claims")


def slot_recall(card: dict, packet: dict) -> float | None:
    """1.0 iff all REQUIRED_SLOTS present and every claim cited in packet.

    None for abstain cards (excluded from denominators, counted separately).
    """
    if _is_abstain(card):
        return None
    texts = {c.get("text") for c in card["claims"]}
    valid = _ids(packet)
    # Every claim cited AND all required slots present (also covers
    # LLM-path cards with extra claims: required set = that card's list).
    if set(REQUIRED_SLOTS) <= texts and all(
        c.get("evidence_id") in valid for c in card["claims"]
    ):
        return 1.0
    return 0.0


def precision_card(card: dict, packet: dict) -> float | None:
    """Fraction of claims whose evidence_id is a packet ID. None if abstain."""
    if _is_abstain(card):
        return None
    valid = _ids(packet)
    hits = sum(1 for c in card["claims"] if c.get("evidence_id") in valid)
    return hits / len(card["claims"])


def claim_recall(card: dict, packet: dict) -> float | None:
    """Fractional required-claim recall: required-claims-cited / required-claims.

    Partial-credit sibling of the binary slot_recall gate (spec task-6-spec.md
    sec 2): template cards (exactly REQUIRED_SLOTS) score cited/3; cards with
    extra claims (future LLM path) score over the card's own claim list.
    None for abstain cards (excluded from denominators, counted separately).
    """
    if _is_abstain(card):
        return None
    claims = card.get("claims", [])
    if not claims:
        return None
    if {c.get("text") for c in claims} == set(REQUIRED_SLOTS):
        required = [c for c in claims if c.get("text") in REQUIRED_SLOTS]
    else:
        required = list(claims)
    valid = _ids(packet)
    cited = sum(1 for c in required if c.get("evidence_id") in valid)
    return cited / len(required)


def coverage_recall(card: dict, packet: dict) -> float | None:
    """Fraction of packet trace (ev-*) IDs cited by >=1 claim. None if abstain."""
    if _is_abstain(card):
        return None
    trace_ids = {t.get("id") for t in packet.get("trace", []) if t.get("id")}
    if not trace_ids:
        return 1.0
    cited = {c.get("evidence_id") for c in card["claims"]}
    return len(trace_ids & cited) / len(trace_ids)


def _render_trace(t: dict) -> str:
    return (
        f"Machine {t.get('machine')} {t.get('own_state', '?')} "
        f"at tick {t.get('onset', '?')} ({t.get('onset_kind', '?')})."
    )


def _render_path(p: dict) -> str:
    return f"Path {'->'.join(p.get('nodes', []) or [])} prob {p.get('prob', 0):.2f}."


def build_premise(packet: dict, claim: dict) -> str:
    """Rendered text of the cited evidence object(s); '' if none cited."""
    eid = claim.get("evidence_id")
    if not eid:
        return ""
    for t in packet.get("trace", []):
        if t.get("id") == eid:
            return _render_trace(t)
    for p in packet.get("paths", []):
        if p.get("id") == eid:
            return _render_path(p)
    if eid == packet.get("id"):
        bits = [_render_trace(t) for t in packet.get("trace", [])]
        bits += [_render_path(p) for p in packet.get("paths", [])]
        return " ".join(b for b in bits if b)
    return ""


def build_hypothesis(claim: dict) -> str:
    """One sentence per claim slot."""
    text, value = claim.get("text"), claim.get("value")
    if text == "origin":
        return f"The fault originated at {value}."
    if text == "onset":
        return f"Onset was tick {value}."
    if text == "causal path":
        nodes = "->".join(value) if isinstance(value, (list, tuple)) else value
        return f"Fault propagated along {nodes}."
    return f"{text}: {value}."


def _majority(labels: list[str]) -> str:
    return Counter(labels).most_common(1)[0][0]


def fmt_rate(n_ok: float, n_total: int) -> str:
    """Rate for operator-visible MEASURED lines.

    Zero denominator (e.g. 100%-abstain corpus) prints as undefined —
    never 0.000, which would read as measured failure.
    """
    if n_total == 0:
        return "undefined (0 non-abstain)"
    return f"{n_ok / n_total:.3f}"


class LocalMnliClient:
    """Local MNLI client with an injectable encode step.

    `encode(premise, hypothesis)` runs the model and returns
    {"label", "prob"}. `order="rev"` swaps premise/hypothesis positions
    before encoding, so the 3-run x 2-order swap gate actually tests
    order bias (a rev that duplicates fwd would make swap_agree
    vacuously True and flip_rate always 0).
    """

    def __init__(self, encode):
        self._encode = encode

    def entails(self, premise, hypothesis, order="fwd"):
        if order == "rev":
            premise, hypothesis = hypothesis, premise
        return self._encode(premise, hypothesis)


def _call_client(client, premise: str, hypothesis: str, order: str) -> dict:
    """Call client.entails, signalling order when the client accepts it."""
    try:
        params = inspect.signature(client.entails).parameters
    except (TypeError, ValueError):
        params = {}
    if "order" in params:
        return client.entails(premise, hypothesis, order=order)
    if order == "fwd":
        return client.entails(premise, hypothesis)
    return client.entails(hypothesis, premise)


def nli_entails(premise: str, hypothesis: str, client=None, runs: int = NLI_RUNS) -> dict:
    """3 runs x 2 orders; majority vote; swap must agree.

    -> {"label", "prob" (mean), "runs", "swap_agree"}.
    label == "unjudged" when the two order-majorities disagree.
    Empty premise -> non-entailment without calling the client
    (recall=1 requires a non-empty cited set).
    """
    if client is None:
        raise NliUnavailable(NLI_SKIP_REASON)
    if not premise:
        return {"label": "neutral", "prob": 0.0, "runs": [], "swap_agree": True}
    fwd = [_call_client(client, premise, hypothesis, "fwd") for _ in range(runs)]
    rev = [_call_client(client, premise, hypothesis, "rev") for _ in range(runs)]
    fwd_maj = _majority([r["label"] for r in fwd])
    rev_maj = _majority([r["label"] for r in rev])
    agree = fwd_maj == rev_maj
    probs = [float(r.get("prob", 0.0)) for r in fwd + rev]
    return {
        "label": fwd_maj if agree else "unjudged",
        "prob": sum(probs) / len(probs),
        "runs": fwd + rev,
        "swap_agree": agree,
    }


def judge_claim(packet: dict, claim: dict, client=None) -> dict:
    """Per-claim entailment verdict + entailed flag."""
    if client is None:
        raise NliUnavailable(NLI_SKIP_REASON)
    r = nli_entails(build_premise(packet, claim), build_hypothesis(claim), client=client)
    r["entailed"] = r["label"] == "entailment" and r["swap_agree"]
    return r


def corpus_nli(items: list[tuple[dict, dict]], client=None) -> dict:
    """Corpus NLI faithfulness; SKIPPED-with-reason when client is None."""
    if client is None:
        return {"status": f"SKIPPED ({NLI_SKIP_REASON})"}
    results = []
    for card, packet in items:
        if _is_abstain(card):
            continue
        for claim in card["claims"]:
            results.append(judge_claim(packet, claim, client=client))
    if not results:
        return {"status": "SKIPPED (no non-abstain claims)", "n_claims": 0}
    flips = sum(1 for r in results if not r["swap_agree"])
    flip_rate = flips / len(results)
    if flip_rate > FLIP_KILL_RATE:
        return {
            "status": f"DROPPED (flip rate {flip_rate:.2f} > {FLIP_KILL_RATE:.2f})",
            "label": "unjudged",
            "swap_agree": False,
            "flip_rate": flip_rate,
            "n_claims": len(results),
        }
    entailed = sum(1 for r in results if r["entailed"])
    return {
        "status": "MEASURED",
        "label": "entailment",
        "swap_agree": True,
        "faithfulness": entailed / len(results),
        "flip_rate": flip_rate,
        "n_claims": len(results),
    }


def client_from_env():
    """Local-model gate: VERDANDI_MNLI_PATH -> client, else NliUnavailable.

    Lazy imports only, so pytest without torch/transformers still passes.
    """
    path = os.environ.get("VERDANDI_MNLI_PATH")
    if not path:
        raise NliUnavailable(NLI_SKIP_REASON)
    if not os.path.exists(path):
        raise NliUnavailable(f"VERDANDI_MNLI_PATH missing: {path}")
    try:
        import torch  # noqa: F401
        import transformers  # noqa: F401
    except ImportError as e:
        raise NliUnavailable(f"NLI stack not installed ({e})")
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    tok = AutoTokenizer.from_pretrained(path, local_files_only=True)
    mdl = AutoModelForSequenceClassification.from_pretrained(path, local_files_only=True)
    mdl.eval()

    def _encode(premise, hypothesis):
        import torch as _t

        enc = tok(premise, hypothesis, return_tensors="pt", truncation=True)
        with _t.no_grad():
            logits = mdl(**enc).logits
        probs = _t.softmax(logits, dim=-1)[0].tolist()
        # MNLI label order: contradiction / neutral / entailment.
        idx = max(range(3), key=lambda i: probs[i])
        return {
            "label": ("contradiction", "neutral", "entailment")[idx],
            "prob": probs[idx],
        }

    return LocalMnliClient(_encode)


def aggregate(items: list[tuple[dict, dict]], client=None) -> dict:
    """Deterministic P/R over non-abstain cards + gated NLI arm."""
    slots, claims, covers, precs = [], [], [], []
    n_abstain = 0
    for card, packet in items:
        if _is_abstain(card):
            n_abstain += 1
            continue
        slots.append(slot_recall(card, packet))
        claims.append(claim_recall(card, packet))
        covers.append(coverage_recall(card, packet))
        precs.append(precision_card(card, packet))
    n = len(slots)
    mean = lambda xs: (sum(xs) / len(xs)) if xs else None
    return {
        "n": n,
        "n_abstain": n_abstain,
        "recall_slot": mean(slots),
        "recall_claim": mean(claims),
        "recall_cover": mean(covers),
        "precision": mean(precs),
        "nli": corpus_nli(items, client=client),
    }
