"""W6 (MINIPRO-22 Todo 6): determinism x5 + wall +2% + Q_DET helper.

Acceptance: `pytest -k "diverge and (777 or 1234 or 999 or 42 or 2026)"`
selects one test per seed and passes with 0-diverge; legacy channels
(obs/states) are byte-identical across same-seed repeats (CH8/CH9 additions
must not perturb them). Wall timing itself is CLI-only
(`twin.py --calibrate` + `check_gates.py --wall-mean`): a 2% band on
~0.11s episodes is noise-dominated, so no timing assertion lives in pytest;
this file pins the Q_DET helper math (pure, deterministic) and the fresh
calibration JSON contract instead. Q_DET helper takes all bars as explicit
arguments — threshold VALUES stay in MINIPRO-10/17, never here and never in
src/twin.py.
"""

import copy
import hashlib
import json

import pytest

from src import twin

pytestmark = pytest.mark.k3

W6_SEEDS = (777, 1234, 999, 42, 2026)
W6_F21 = {
    "id": "F-21",
    "class": "drift",
    "origin": "B2",
    "t0": 150,
    "dur": 12,
    "mag_sigma": 5.2,
}


def q_det_digest(rec_a, rec_b):
    digest_a = twin.replay_digest(rec_a)
    digest_b = twin.replay_digest(rec_b)
    return digest_a, digest_b, 0 if rec_a == rec_b else 1


def q_det_wall(wall_s, fresh_mean_s, factor):
    budget_s = fresh_mean_s * factor
    return budget_s, wall_s <= budget_s, wall_s / fresh_mean_s


def _legacy_channels_digest(rec):
    blob = json.dumps(
        {"obs": rec["obs"], "states": rec["states"]},
        sort_keys=True,
        default=repr,
    ).encode()
    return hashlib.sha256(blob).hexdigest()


@pytest.mark.parametrize("seed", W6_SEEDS)
def test_diverge_zero_repeat_seed(seed):
    rec_a = twin.run_episode(seed, copy.deepcopy(W6_F21))
    rec_b = twin.run_episode(seed, copy.deepcopy(W6_F21))
    digest_a, digest_b, diverge = q_det_digest(rec_a, rec_b)
    assert digest_a == digest_b
    assert diverge == 0
    assert _legacy_channels_digest(rec_a) == _legacy_channels_digest(rec_b)


@pytest.mark.parametrize("seed", W6_SEEDS)
def test_diverge_zero_repeat_clean_seed(seed):
    rec_a = twin.run_episode(seed, None)
    rec_b = twin.run_episode(seed, None)
    _, _, diverge = q_det_digest(rec_a, rec_b)
    assert diverge == 0
    assert _legacy_channels_digest(rec_a) == _legacy_channels_digest(rec_b)


def test_q_det_wall_math_pure():
    budget, ok, ratio = q_det_wall(0.10, 0.10, 1.02)
    assert budget == pytest.approx(0.102)
    assert ok is True
    assert ratio == pytest.approx(1.0)
    _, ok_over, _ = q_det_wall(0.103, 0.10, 1.02)
    assert ok_over is False


def test_calibrate_writes_fresh_mean_json(tmp_path):
    cal_path = str(tmp_path / "w6-fresh-calibration.json")
    twin._calibrate(cal_path)
    with open(cal_path) as fh:
        payload = json.load(fh)
    assert payload["mean_per_episode_s"] > 0
    assert payload["seeds"] == [7, 11, 13]
    assert payload["episodes_timed"] == 6 == len(payload["episodes"])
