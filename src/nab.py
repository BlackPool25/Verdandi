"""NAB-style event scoring (deployment verdict for detectors).

Per fault episode: a hit is any alarm at/after onset within the anomaly span;
earlier alarms score higher (sigmoidal early-detection credit). Alarms on
clean episodes and outside all spans count as false positives. Application
profiles weight the two error types: 'standard' (balanced), 'low-fn'
(missed faults cost double — factory outage regime), 'low-fp' (alarms are
expensive — inspection regime).
"""

from __future__ import annotations

import math

PROFILES = {
    "standard": {"w_fn": 1.0, "w_fp": 1.0},
    "low-fn": {"w_fn": 2.0, "w_fp": 1.0},
    "low-fp": {"w_fn": 1.0, "w_fp": 2.0},
}


def early_credit(delay_ticks: int, span_ticks: int) -> float:
    """Sigmoidal early-detection credit: 1.0 at onset, decaying after."""
    if delay_ticks < 0:
        return 0.0
    x = delay_ticks / max(1.0, float(span_ticks))
    return 2.0 / (1.0 + math.exp(5.0 * x)) if x <= 1.0 else 0.0


def nab_event_score(
    hits: list[tuple[bool, int, int]],
    clean_episodes: int,
    clean_alarms: int,
    *,
    profile: str = "standard",
) -> dict:
    """Score a detector from per-episode outcomes.

    hits: [(hit, delay_ticks, span_ticks)] per fault episode.
    Returns hit_rate, mean credit over hits, clean FP rate, and the
    profile-weighted score in [0, 1].
    """
    if profile not in PROFILES:
        raise ValueError(f"unknown profile {profile!r}")
    w = PROFILES[profile]
    n = len(hits)
    rate = sum(1 for h, _, _ in hits if h) / n if n else 0.0
    credit = (
        sum(early_credit(d, s) for h, d, s in hits if h)
        / max(1, sum(1 for h, _, _ in hits if h))
        if n
        else 0.0
    )
    fp_rate = clean_alarms / clean_episodes if clean_episodes else 0.0
    score = max(0.0, (rate * credit * w["w_fn"] - fp_rate * w["w_fp"]) / w["w_fn"])
    return {
        "hit_rate": float(rate),
        "mean_credit": float(credit),
        "clean_fp_rate": float(fp_rate),
        "score": float(min(1.0, score)),
        "profile": profile,
    }
