"""T2-owned SSE replay helpers (T1 skeleton: store + formatter only).

Demo-transport waiver: this SSE replay is a demo viewer, not the killed
prod live-stream path (SIM_SPEC section 1.3 non-goals: `live stream` stays
dead; the server precomputes one whole episode and replays it tick by
tick). T2 fills in the 300-tick replay; T1 only needs the module to exist.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

# In-memory episode registry, keyed by episode_id. T2 adds the precomputed
# record + 300-tick cursor here; T1 stores the validated request envelope.
EPISODES: dict[str, dict[str, Any]] = {}


def format_sse(event: str, data: dict[str, Any]) -> str:
    """Format one SSE frame (T2 reuses this for tick streaming)."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def build_header(episode_id: str, record: dict[str, Any], digest: str) -> dict[str, Any]:
    """Episode-final header: sbuf/flow finals + c7tail_final + digest."""
    return {
        "episode_id": episode_id,
        "seed": record["seed"],
        "T": record["T"],
        "replay_digest": digest,
        "sbuf_stats": record["sbuf_stats"],
        "flow_stats": record["flow_stats"],
        "c7tail_final": record["flow_stats"]["c7tail"],
        "faults": record["faults"],
    }


def build_tick(record: dict[str, Any], step: int) -> dict[str, Any]:
    """One replay row in the T3 frozen schema (delegates to schema.build_tick).

    Single source of truth for tick shape lives in schema.py (T3-owned);
    T2 only replays. Keys exactly TICK_KEYS: throughput (not tput) plus
    sparse parts[]-last quality join.
    """
    from services.sim_bridge.schema import build_tick as schema_build_tick

    return schema_build_tick(record, step)


def replay_frames(
    episode_id: str, record: dict[str, Any], digest: str, from_step: int = 0
) -> Iterator[str]:
    """Yield header + tick frames from from_step..T-1 (cursor-only replay)."""
    yield format_sse("header", build_header(episode_id, record, digest))
    for step in range(from_step, record["T"]):
        yield format_sse("tick", build_tick(record, step))
