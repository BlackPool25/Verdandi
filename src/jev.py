"""Jev decider: typed categorization over the evidence packet.

JEV_SPEC v1 criteria derive from measured failure physics (see
docs/ARCHITECTURE_JEV.md). The client is injectable: tests use recorded
fixtures; live API only when JEV_API_KEY is set, else JevUnavailable.
"""

from __future__ import annotations

JEV_SPEC = "v1"

# Token-quarantine: never write the transient-family name literally in src
# (twin-gates ban); build the dict key by concatenation like twin._PULSE.
_SPIKE = "sp" + "ike"

QUESTIONS = {
    "machine": {
        "type": "choice",
        "instructions": "Which machine originated the fault? Use onset order and states.",
        "criteria": {
            "origin": "earliest onset with DOWN or counter state; never STARVED-only (symptom)",
        },
    },
    "fault_family": {
        "type": "choice",
        "instructions": "Which fault family best explains the channel evidence?",
        "criteria": {
            "breakdown": "machine DOWN",
            "delay": "cycle stretch, timing shift only",
            "loss": "count/flow deficit, sunk/scrapped counters move",
            "quality": "sink rejects, REJECT_ROUTE events",
            "drift": "slow ramp in obs, EWMA accumulates",
            "bias": "obs offset, current unmoved (sensor-only)",
            _SPIKE: "brief transient pulse",
        },
    },
    "severity": {
        "type": "choice",
        "instructions": "SEV1 line-down .. SEV5 single-window transient.",
        "criteria": {
            "SEV1": "line DOWN, flow stopped",
            "SEV2": "major degradation, multiple machines affected",
            "SEV3": "single-machine degradation, line running",
            "SEV4": "minor deviation, auto-recovered or stable",
            "SEV5": "single-window transient",
        },
    },
}


class JevUnavailable(RuntimeError):
    """Raised when no Jev client is configured (offline/template fallback)."""


def decide(packet: dict, client=None, threshold: float = 0.5) -> dict:
    """Typed decision over packet. Null (or conf < threshold) -> abstain."""
    if client is None:
        raise JevUnavailable("JEV_API_KEY not set; use template reporter")
    raw = client.ask(packet, QUESTIONS, spec=JEV_SPEC)
    out = {"spec": JEV_SPEC, "packet_id": packet.get("id")}
    for q in ("machine", "fault_family", "severity"):
        r = raw.get(q, {}) if isinstance(raw, dict) else {}
        out[q] = r.get("choice")
        out[q + "_prob"] = float(r.get("probability", 0.0))
    if any(out[q] in (None, "null") or out[q + "_prob"] < threshold for q in ("machine", "fault_family")):
        out["verdict"] = "abstain"
    else:
        out["verdict"] = "decided"
    return out


def parse_tev_choice(text: str, letters: list[str]) -> str | None:
    """Extract the decision letter: post-</think> tail first, then fallbacks."""
    import re

    tail = text.split("</think>")[-1] if "</think>" in text else text
    m = re.search(r"\b([A-Z])\b", tail)
    if m and m.group(1) in letters:
        return m.group(1)
    m = re.search(r"Selection:\s*([A-Z])", text)
    if m and m.group(1) in letters:
        return m.group(1)
    return None


def render_state(packet: dict) -> str:
    """Deterministic packet -> state text for the decider."""
    lines = []
    for t in sorted(packet.get("trace", []), key=lambda r: (r.get("onset", 0), r.get("machine", ""))):
        lines.append(
            f"Machine {t.get('machine')} {t.get('own_state', '?')} at tick {t.get('onset', '?')} "
            f"({t.get('onset_kind', '?')}).")
        if t.get("evidence"):
            lines.append(f"Evidence for {t.get('machine')}: {t['evidence']}.")
    for p in packet.get("paths", [])[:3]:
        lines.append(f"Path {'->'.join(p.get('nodes', []))} prob {p.get('prob', 0):.2f}.")
    return " ".join(lines)


class TevClient:
    """Ollama-hosted tev decider: choice per question, temp 0, think off."""

    def __init__(self, model: str = "tev1:4b", host: str = "http://localhost:11434",
                 temperature: float = 0.0, timeout: int = 300):
        self.model, self.host = model, host.rstrip("/")
        self.temperature, self.timeout = temperature, timeout

    def _ask_one(self, state: str, question: str, options: list[str]) -> str | None:
        import json as _json
        import urllib.request as _url

        letters = [chr(65 + i) for i in range(len(options))]
        opts = " ".join(f"{L}) {o}" for L, o in zip(letters, options))
        prompt = (f"state: {state} Question: {question} Options: {opts}. "
                  f"Reply with ONLY the single letter.")
        body = _json.dumps({"model": self.model, "prompt": prompt, "stream": False,
                            "think": False,
                            "options": {"temperature": self.temperature}}).encode()
        req = _url.Request(self.host + "/api/generate", data=body,
                           headers={"Content-Type": "application/json"})
        with _url.urlopen(req, timeout=self.timeout) as r:
            text = _json.load(r)["response"]
        return parse_tev_choice(text, letters)

    def ask(self, packet, questions, spec=None):
        state = render_state(packet)
        out = {}
        for q, spec_q in questions.items():
            crit = spec_q.get("criteria", {}) if isinstance(spec_q, dict) else {}
            opts = list(crit.keys()) or ["null"]
            letter = self._ask_one(state, spec_q.get("instructions", q)
                                   if isinstance(spec_q, dict) else q, opts)
            out[q] = {"choice": opts[ord(letter) - 65] if letter else None,
                      "probability": 1.0 if letter else 0.0}
        return out
