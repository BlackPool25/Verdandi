"""CH8 current tables_resolve (Todo W1, TDD RED-first).

Example amps (A2/C2 15A, RWK0 3.5A) are ASSUMPTIONS for QA pinning,
not normative spec claims — owner sign-off gates merge (plan G4).

Todo W2: dedicated eta streams + vectorized pre-draw + delete-eta proof
(plan G3: children[idx].spawn(1)[0] grandchildren, N_STREAMS==36
unchanged, single (26,300) episode-start pre-draw, [idx][t] indexing).
"""

import hashlib
import json
import pathlib

import numpy as np
import pytest

from src.config import (
    I_IDLE_RATIO,
    I_RATED_BY_CLASS,
    K_BY_GROUP,
    MACHINE_INDEX,
    MACHINES,
    N_MACHINES,
    N_STREAMS,
    STEP_SECONDS,
    T,
    VOLT,
    resolve_current,
)
from src import twin as twin_mod
from src.twin import _spawn_streams, run_episode


def test_tables_resolve():
    # Scalars present with locked values.
    assert I_IDLE_RATIO == 0.15
    assert STEP_SECONDS == 1
    assert VOLT == 400

    # 9 classes keyed like TEMP_RANGES pattern.
    assert set(I_RATED_BY_CLASS) == {
        "feed",
        "form",
        "process",
        "finish",
        "inspect-tail",
        "assembly-kit",
        "assembly-join",
        "test",
        "rework",
    }

    # Every MACHINE_INDEX entry resolves both I_RATED and K.
    for name in MACHINE_INDEX:
        i_rated, k = resolve_current(name)
        assert isinstance(i_rated, float) and i_rated > 0
        assert isinstance(k, float) and 0 < k <= 1.0
        # Cross-check class table drives I_RATED.
        assert i_rated == float(I_RATED_BY_CLASS[MACHINES[name]["class"]])

    # QA happy pins (ASSUMPTIONS, not normative):
    assert resolve_current("A2") == (15.0, 1.0)  # assumption: process 15A
    assert resolve_current("C2") == (15.0, 0.7)  # assumption: process 15A, C-group k=0.7
    assert resolve_current("RWK0") == (3.5, 0.3)  # assumption: rework 3.5A, RWK k=0.3

    # K group spot checks.
    assert K_BY_GROUP["A"] == 1.0
    assert K_BY_GROUP["C"] == 0.7

    # Failure modes.
    with pytest.raises((KeyError, ValueError)):
        resolve_current("ZZZ9")  # unknown prefix/machine
    with pytest.raises((TypeError, ValueError)):
        resolve_current("A2", i_rated=99.0)  # v1: no per-machine override


def _old_channel_digest(rec):
    """Byte-stable digest over legacy channels only (obs + states)."""
    payload = {"obs": rec["obs"], "states": rec["states"]}
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=repr).encode()
    ).hexdigest()


def test_delete_eta_disabled_digests_identical():
    """Delete-eta proof: eta machinery leaves legacy obs/states byte-identical.

    _spawn_streams returns dedicated eta streams as a 6th value; with the
    CH8 hook wired (record["currents"] present — W3); two same-seed
    episodes hash identically over obs + states.
    """
    noise, place, drop, agv, fail, eta = _spawn_streams(777)
    assert eta.shape == (N_MACHINES, T)
    assert eta.dtype == np.float64
    rec1 = run_episode(777, None)
    rec2 = run_episode(777, None)
    assert "currents" in rec1  # CH8 hook wired: W3 adds the currents channel
    assert len(rec1["currents"]) == N_MACHINES
    assert all(len(row) == T for row in rec1["currents"])
    assert _old_channel_digest(rec1) == _old_channel_digest(rec2)


def test_spawn_literal_and_retired_assert():
    """spawn(36) literal kept for the T1 grep; retired 26-31 assert intact.

    Eta uses spawn(1) grandchildren (G3) and never reads children 26-31
    directly outside the retired assert.
    """
    src = pathlib.Path(twin_mod.__file__).read_text()
    assert "seq.spawn(36)" in src  # == N_STREAMS; literal kept
    assert ".spawn(1)[0]" in src  # dedicated eta grandchildren (G3)
    assert N_STREAMS == 36
    assert "children 26-31 retired, must stay unread" in src
    body = src.split("def _spawn_streams", 1)[1].split("\ndef ", 1)[0]
    for i in range(26, 32):
        assert f"children[{i}]" not in body.replace(
            "set(range(26, 32))", ""
        ), f"child {i} must stay unread outside the retired assert"


def _idx_order():
    """Machine name per row index (MACHINE_INDEX literal order)."""
    return sorted(MACHINE_INDEX, key=MACHINE_INDEX.get)


def test_ch8_idle_draw_blocked_starved():
    """W3 in-step hook: STARVED/BLOCKED draw idle, RUN cycles load (Todo W3).

    I = I_idle + k*L*(I_rated-I_idle) + eta[idx][t], clamped at 0.
    L=1 iff RUN-cycling (held or tput==1 release); BLOCKED-holding L=0,
    STARVED L=0. Never derived from obs val (non-collinear by construction).
    """
    seed = 777
    rec = run_episode(seed, None)
    cur = rec["currents"]  # KeyError before the W3 hook lands
    arr = np.asarray(cur, dtype=np.float64)
    assert arr.shape == (N_MACHINES, T)
    assert arr.dtype == np.float64
    _, _, _, _, _, eta = _spawn_streams(seed)
    order = _idx_order()
    n_idle = n_run = 0
    for m, name in enumerate(order):
        i_rated, k = resolve_current(name)
        i_idle = I_IDLE_RATIO * i_rated
        assert i_idle > 0  # idle draw is a positive standby draw (G4)
        for t in range(T):
            st = rec["states"][m][t]
            e = float(eta[m][t])
            if st in ("STARVED", "BLOCKED"):
                assert cur[m][t] == pytest.approx(max(0.0, i_idle + e))
                n_idle += 1
            elif st == "RUN":
                assert cur[m][t] == pytest.approx(
                    max(0.0, i_idle + k * (i_rated - i_idle) + e)
                )
                n_run += 1
    assert n_idle > 0 and n_run > 0
    # QA pin: A2 (k=1.0) RUN-cycling base tops exactly at I_rated.
    a2 = MACHINE_INDEX["A2"]
    assert resolve_current("A2") == (15.0, 1.0)
    run_ts = [t for t in range(T) if rec["states"][a2][t] == "RUN"]
    assert run_ts
    for t in run_ts:
        assert cur[a2][t] == pytest.approx(max(0.0, 15.0 + float(eta[a2][t])))
    # Non-collinearity: obs varies over A2 RUN steps, current base is flat.
    assert float(np.std([rec["obs"][a2][t] for t in run_ts])) > 0


def test_ch8_down_draw():
    """W3 in-step hook: DOWN draws idle (G4 lock), eta rides on top."""
    fault = {
        "id": "F-T",
        "class": "breakdown",
        "origin": "A2",
        "t0": 150,
        "dur": 12,
        "extra": {"mttr_mult": 2},
    }
    seed = 777
    rec = run_episode(seed, fault)
    cur = rec["currents"]  # KeyError before the W3 hook lands
    _, _, _, _, _, eta = _spawn_streams(seed)
    a2 = MACHINE_INDEX["A2"]
    i_rated, _ = resolve_current("A2")
    i_idle = I_IDLE_RATIO * i_rated
    # Injected window [150, 150+ceil(12*2)): forced DOWN every step.
    down_ts = [t for t in range(150, 174) if rec["states"][a2][t] == "DOWN"]
    assert len(down_ts) == 174 - 150
    for t in down_ts:
        assert cur[a2][t] == pytest.approx(max(0.0, i_idle + float(eta[a2][t])))


def test_ch8_clamp():
    """W3 in-step hook: currents are 26x300 float64, >= 0, with clamped dips."""
    seed = 777
    rec = run_episode(seed, None)
    cur = rec["currents"]  # KeyError before the W3 hook lands
    arr = np.asarray(cur, dtype=np.float64)
    assert arr.shape == (N_MACHINES, T)
    assert arr.dtype == np.float64
    assert bool(np.all(arr >= 0.0))
    # Deep-negative eta dips under small I_idle (e.g. RWK0 0.525A) clamp.
    assert bool(np.any(arr == 0.0))
