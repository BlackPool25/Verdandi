"""T2-owned replay check: POST /episode precompute + 300-tick SSE replay.

Boots TestClient (no live server needed). Asserts 300 ticks, per-tick
shapes, digest equality across two POSTs, and from_step resume identity.
Prints PASS + byte budget. Usage: python services/sim_bridge/scripts/check_replay.py --seed 777
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3]))

from fastapi.testclient import TestClient

from services.sim_bridge.app import app
from services.sim_bridge.schema import TICK_KEYS, validate_tick

FAULT = {
    "id": "F-21",
    "class": "drift",
    "origin": "B5",
    "t0": 150,
    "dur": 12,
    "mag_sigma": 5.2,
}


def parse_sse(text: str):
    header = None
    ticks = []
    for chunk in text.strip().split("\n\n"):
        lines = chunk.strip().splitlines()
        event = next(l[7:] for l in lines if l.startswith("event: "))
        data = json.loads(next(l[6:] for l in lines if l.startswith("data: ")))
        if event == "header":
            header = data
        else:
            ticks.append(data)
    return header, ticks


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=777)
    args = ap.parse_args()
    client = TestClient(app)

    bodies = []
    for _ in range(2):
        r = client.post("/episode", json={"seed": args.seed, "faults": FAULT})
        assert r.status_code == 200, r.text
        bodies.append(r.json())
    a, b = bodies
    assert a["episode_id"] != b["episode_id"], "ids must differ per POST"
    assert a["replay_digest"] == b["replay_digest"], "same seed+fault must give same digest"
    print(f"digest={a['replay_digest']} ids={a['episode_id'][:8]}..,{b['episode_id'][:8]}..")

    full = client.get(f"/stream?episode_id={a['episode_id']}")
    assert full.status_code == 200, full.text
    header, ticks = parse_sse(full.text)
    assert len(ticks) == 300, f"want 300 ticks, got {len(ticks)}"
    assert [t["step"] for t in ticks] == list(range(300))
    for t in ticks:
        assert set(t) == set(TICK_KEYS), f"tick keys drift: {sorted(set(t) ^ set(TICK_KEYS))}"
        assert len(t["states"]) == 32 and len(t["obs"]) == 32
        assert len(t["throughput"]) == 32 and len(t["buffers"]) == 31
    for k in (0, 150, 299):
        validate_tick(ticks[k])
    print("schema=validate_tick(0,150,299) OK")
    assert header["c7tail_final"] == header["flow_stats"]["c7tail"]
    assert header["replay_digest"] == a["replay_digest"]

    resumed = client.get(f"/stream?episode_id={a['episode_id']}&from_step=150")
    _, ticks150 = parse_sse(resumed.text)
    assert len(ticks150) == 150 and ticks150[0]["step"] == 150
    assert ticks150[0] == ticks[150], "resume row 150 must equal full-run row 150"

    nbytes = len(full.text.encode())
    print(f"ticks=300 steps=0..299 shapes=32/32/32/31 resume150=identical bytes={nbytes}")
    print("PASS")


if __name__ == "__main__":
    main()
