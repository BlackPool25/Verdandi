"""T2 failing-first: batch precompute + 300-tick SSE replay + determinism.

RED STEP: GET /stream does not exist yet — every test here MUST fail
(404) until T2 wires precompute + replay. No twin stepper is added;
POST /episode calls run_episode once and caches the record.
"""

from fastapi.testclient import TestClient

from services.sim_bridge.app import app
from services.sim_bridge.schema import TICK_KEYS, validate_tick

client = TestClient(app)

_PROBE_FAULT = {
    "id": "F-21",
    "class": "drift",
    "origin": "B2",
    "t0": 150,
    "dur": 12,
    "mag_sigma": 5.2,
}


def _post_episode(seed=777, faults=None):
    body = {"seed": seed}
    if faults is not None:
        body["faults"] = faults
    r = client.post("/episode", json=body)
    assert r.status_code == 200, r.text
    return r.json()


def _sse_rows(res):
    """Split an SSE body into (header, [tick datas]) as parsed JSON."""
    import json

    header = None
    ticks = []
    for chunk in res.text.strip().split("\n\n"):
        lines = chunk.strip().splitlines()
        event = next(l[7:] for l in lines if l.startswith("event: "))
        data = json.loads(next(l[6:] for l in lines if l.startswith("data: ")))
        if event == "header":
            header = data
        elif event == "tick":
            ticks.append(data)
    return header, ticks


def test_post_precomputes_digest():
    body = _post_episode(777, _PROBE_FAULT)
    assert body["replay_digest"], "POST /episode must return replay_digest"
    assert body["episode_id"]


def test_stream_replays_exactly_300_ticks():
    body = _post_episode(777, _PROBE_FAULT)
    res = client.get(f"/stream?episode_id={body['episode_id']}")
    assert res.status_code == 200, res.text
    header, ticks = _sse_rows(res)
    assert header is not None
    assert len(ticks) == 300
    assert [t["step"] for t in ticks] == list(range(300))


def test_tick_shapes_and_header_finals():
    body = _post_episode(777, _PROBE_FAULT)
    res = client.get(f"/stream?episode_id={body['episode_id']}")
    header, ticks = _sse_rows(res)
    for t in ticks:
        assert set(t) == set(TICK_KEYS)
        assert len(t["states"]) == 26
        assert len(t["obs"]) == 26
        assert len(t["throughput"]) == 26
        assert len(t["buffers"]) == 26
    assert {"sbuf_stats", "flow_stats", "c7tail_final",
            "replay_digest"} <= set(header)


def test_live_rows_match_frozen_schema():
    body = _post_episode(777, _PROBE_FAULT)
    _, ticks = _sse_rows(client.get(f"/stream?episode_id={body['episode_id']}"))
    for k in (0, 150, 299):
        assert ticks[k]["step"] == k
        validate_tick(ticks[k])


def test_same_seed_fault_twice_identical_digest_and_rows():
    first = _post_episode(777, _PROBE_FAULT)
    second = _post_episode(777, _PROBE_FAULT)
    assert first["episode_id"] != second["episode_id"]
    assert first["replay_digest"] == second["replay_digest"]
    _, ticks_a = _sse_rows(client.get(f"/stream?episode_id={first['episode_id']}"))
    _, ticks_b = _sse_rows(client.get(f"/stream?episode_id={second['episode_id']}"))
    assert ticks_a == ticks_b


def test_from_step_resumes_identical_row():
    body = _post_episode(777, _PROBE_FAULT)
    _, full = _sse_rows(client.get(f"/stream?episode_id={body['episode_id']}"))
    res = client.get(f"/stream?episode_id={body['episode_id']}&from_step=150")
    assert res.status_code == 200, res.text
    _, resumed = _sse_rows(res)
    assert len(resumed) == 150
    assert resumed[0]["step"] == 150
    assert resumed[0] == full[150]


def test_unknown_episode_404():
    res = client.get("/stream?episode_id=does-not-exist")
    assert res.status_code == 404


def test_v1_32tick_rejected_non_comparable():
    import copy

    import pytest

    from services.sim_bridge import schema as S
    from src.twin import run_episode

    rec = run_episode(777, _PROBE_FAULT)
    tick = S.build_tick(rec, 0)
    # V1_TICK: saved 32-machine tick shape (states/obs/tput 32, buffers 31)
    v1_tick = copy.deepcopy(tick)
    v1_tick["states"] = tick["states"] + tick["states"][:6]
    v1_tick["obs"] = tick["obs"] + tick["obs"][:6]
    v1_tick["throughput"] = tick["throughput"] + tick["throughput"][:6]
    v1_tick["buffers"] = tick["buffers"] + tick["buffers"][:5]
    assert (len(v1_tick["states"]), len(v1_tick["buffers"])) == (32, 31)
    with pytest.raises(S.SchemaViolation, match="schema v1 non-comparable, rebaseline"):
        S.validate_tick(v1_tick)


def test_bridge_digest_matches_twin_and_golden():
    import json
    import pathlib

    from src.twin import replay_digest, run_episode

    body = _post_episode(777, _PROBE_FAULT)
    twin_digest = replay_digest(run_episode(777, _PROBE_FAULT))
    assert body["replay_digest"] == twin_digest
    golden_path = pathlib.Path(__file__).resolve().parents[1] / "golden" / "replay-777-topology-A.json"
    if golden_path.exists():
        golden = json.loads(golden_path.read_text())
        assert golden["digest"] == twin_digest
        assert golden["code_version"] == "twin-2.1.0-topology-A"
