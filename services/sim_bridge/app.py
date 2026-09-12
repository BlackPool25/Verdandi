"""Sim bridge skeleton (T1): validation mirror + health.

Demo-transport waiver: POST /episode validates and registers an episode;
the tick-by-tick SSE replay in sse.py is a demo viewer, not the killed
prod live-stream path (SIM_SPEC section 1.3 non-goals). T2 adds batch
precompute + 300-tick replay on top of this contract.

Scope: imports ONLY src.twin/src.config (never spike/).
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

from services.sim_bridge.models import (
    BridgeStrictError,
    TwinMirrorError,
    validate_episode,
)
from services.sim_bridge.sse import EPISODES, replay_frames

app = FastAPI(title="sim_bridge")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/episode")
async def create_episode(req: Request) -> JSONResponse:
    """Validate like twin._validate (mirror) + bridge-strict superset.

    The body is read as raw JSON (loose types) so twin-mirror failures
    carry twin-verbatim text instead of framework coercion messages.
    """
    try:
        body: Any = await req.json()
    except ValueError:
        return JSONResponse(status_code=422, content={"detail": "invalid JSON body"})
    if not isinstance(body, dict):
        return JSONResponse(status_code=422, content={"detail": "body must be a JSON object"})
    seed: Any = body.get("seed")
    fault: Any = body.get("faults", body.get("fault", None))
    enable_natural_breakdown: Any = body.get("enable_natural_breakdown", True)
    try:
        result = validate_episode(seed, fault)
    except TwinMirrorError as e:
        return JSONResponse(status_code=422, content={"detail": str(e)})
    except BridgeStrictError as e:
        return JSONResponse(status_code=422, content={"detail": str(e)})
    episode_id = str(uuid.uuid4())
    # T2 batch precompute: run the whole episode once server-side (no twin
    # stepper, no partial compute) and cache the record for cursor replay.
    from src.twin import replay_digest, run_episode

    record = run_episode(seed, result.faults, enable_natural_breakdown=bool(enable_natural_breakdown))
    digest = replay_digest(record)
    EPISODES[episode_id] = {
        "seed": seed,
        "faults": result.faults,
        "enable_natural_breakdown": enable_natural_breakdown,
        "record": record,
        "replay_digest": digest,
    }
    return JSONResponse(
        status_code=200,
        content={
            "episode_id": episode_id,
            "seed": seed,
            "faults": result.faults,
            "enable_natural_breakdown": enable_natural_breakdown,
            "noop_warning": result.noop_warning,
            "replay_digest": digest,
        },
    )


@app.get("/stream", response_model=None)
def stream_episode(episode_id: str, from_step: int = 0):
    """Replay the cached record as header + 300 tick SSE frames.

    Cursor-only controls: pause/resume/speed/step move from_step, never
    recompute. Unknown id -> 404; out-of-range cursor -> 422.
    """
    entry = EPISODES.get(episode_id)
    if entry is None or "record" not in entry:
        return JSONResponse(status_code=404, content={"detail": "unknown episode_id"})
    record = entry["record"]
    if not isinstance(from_step, int) or isinstance(from_step, bool) or not 0 <= from_step < record["T"]:
        return JSONResponse(
            status_code=422, content={"detail": f"from_step out of range: {from_step!r}"}
        )
    return StreamingResponse(
        replay_frames(episode_id, record, entry["replay_digest"], from_step),
        media_type="text/event-stream",
    )


# T3-schema-anchor (T3 owns everything below this line: GET /schema + schema files).


# T3-schema-anchor (T3 owns everything below; do not edit above for schema work)
@app.get("/schema")
def get_schema() -> dict:
    """Return the frozen tick schema (T3 contract lock, read-only)."""
    from services.sim_bridge.schema import FROZEN_SCHEMA

    return dict(FROZEN_SCHEMA)
