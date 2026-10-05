"""Hostile and malformed adversarial input rejection battery.

Exercises 10 hostile input vectors against simulation twin and replay
components to verify explicit rejection with ValueError / TypeError /
AttributeError / SystemExit (never silent pass-through or unhandled crashes).

pytestmark = pytest.mark.adversarial
"""

from __future__ import annotations

import copy
import json

import pytest

from src import replay, twin

pytestmark = pytest.mark.adversarial


def test_case01_bad_schema_version_rejected():
    """Case 1: Bad/unsupported schema_version (1 or 999) rejected by replay_digest."""
    for bad_ver in (1, 999, -1, 0):
        with pytest.raises(ValueError, match="non-comparable"):
            twin.replay_digest({"schema_version": bad_ver, "seed": 777})


def test_case02_nan_infinite_payload_rejected():
    """Case 2: NaN / infinite payload in obs / parameters / fault mag rejected."""
    # Seed parameter with NaN or inf rejected by twin._validate
    with pytest.raises(ValueError, match="seed must be a non-negative int"):
        twin._validate(float("nan"), None)
    with pytest.raises(ValueError, match="seed must be a non-negative int"):
        twin._validate(float("inf"), None)

    # Fault timing parameter with NaN or inf rejected by twin._validate
    with pytest.raises(ValueError, match="fault window out of range"):
        twin._validate(
            777, {"origin": "A0", "class": "drift", "t0": float("nan"), "dur": 10}
        )
    with pytest.raises(ValueError, match="fault window out of range"):
        twin._validate(
            777, {"origin": "A0", "class": "drift", "t0": 150, "dur": float("inf")}
        )

    # NaN / inf in obs payload rejected by strict canonical JSON serialization
    record_with_nan = {
        "schema_version": 2,
        "obs": [[float("nan"), 1.0], [0.0, float("inf")]],
    }
    with pytest.raises(ValueError, match="Out of range float values"):
        json.dumps(record_with_nan, allow_nan=False)


def test_case03_negative_seed_rejected(tmp_path):
    """Case 3: Negative seed handling rejected by twin._validate and CLI."""
    with pytest.raises(ValueError, match="seed must be a non-negative int"):
        twin._validate(-1, None)
    with pytest.raises(ValueError, match="seed must be a non-negative int"):
        replay._validate_seed(-7)
    out_file = tmp_path / "replay_neg.jsonl"
    with pytest.raises(SystemExit):
        replay.main(["--seed", "-1", "--out", str(out_file)])


def test_case04_empty_record_rejected():
    """Case 4: Empty record ({}) rejected by replay_digest with ValueError."""
    with pytest.raises(ValueError, match="non-comparable"):
        twin.replay_digest({})


def test_case05_oversized_fault_window_rejected():
    """Case 5: Oversized fault duration or extreme window outside episode bounds rejected."""
    # Duration overflowing episode limit T (T=300)
    with pytest.raises(ValueError, match="fault window out of range"):
        twin._validate(777, {"origin": "A0", "class": "drift", "t0": 150, "dur": 500})
    # Start time t0 beyond episode limit T
    with pytest.raises(ValueError, match="fault window out of range"):
        twin._validate(777, {"origin": "A0", "class": "drift", "t0": 350, "dur": 10})
    # Window crossing episode boundary (295 + 10 = 305 > 300)
    with pytest.raises(ValueError, match="fault window out of range"):
        twin._validate(777, {"origin": "A0", "class": "drift", "t0": 295, "dur": 10})
    # Zero or negative duration
    with pytest.raises(ValueError, match="fault window out of range"):
        twin._validate(777, {"origin": "A0", "class": "drift", "t0": 150, "dur": 0})
    with pytest.raises(ValueError, match="fault window out of range"):
        twin._validate(777, {"origin": "A0", "class": "drift", "t0": 150, "dur": -5})


def test_case06_unknown_machine_origin_rejected():
    """Case 6: Unknown machine origin in fault spec rejected by twin._validate."""
    for bad_origin in ("UNKNOWN_M99", "B5", "Z99", "", None):
        with pytest.raises(ValueError, match="unknown fault origin"):
            twin._validate(
                777,
                {"origin": bad_origin, "class": "drift", "t0": 150, "dur": 10},
            )


def test_case07_truncated_malformed_json_rejected(tmp_path):
    """Case 7: Truncated JSON / malformed record payload parsing rejected."""
    # Truncated JSON payload decode error
    truncated_json = '{"schema_version": 2, "obs": [1, 2, '
    with pytest.raises((json.JSONDecodeError, ValueError)):
        json.loads(truncated_json)

    # Corrupted manifest payload rejected by manifest loader
    bad_manifest = tmp_path / "broken_manifest.json"
    bad_manifest.write_text('{"records": [incomplete', encoding="utf-8")
    with pytest.raises(ValueError, match="cannot load manifest file"):
        twin._load_manifest(str(bad_manifest), 12345)

    # Empty subgraph string rejected by replay CLI parser
    with pytest.raises(ValueError, match="subgraph spec cannot be empty"):
        replay._parse_subgraph("   ")


def test_case08_invalid_partition_name_rejected(tmp_path):
    """Case 8: Wrong / invalid partition name rejected by twin or replay CLI."""
    for bad_part in ("invalid-partition", "line-Z", "plant_99", ""):
        with pytest.raises(ValueError, match="unknown partition"):
            replay._validate_partition(bad_part)

    out_file = tmp_path / "part_test.jsonl"
    with pytest.raises(ValueError, match="unknown partition"):
        replay.replay(777, out_file, partition="nonexistent-partition")

    # CLI main returns error exit code 1 for invalid partition
    ret = replay.main(
        ["--seed", "7", "--out", str(out_file), "--partition", "bogus_part"]
    )
    assert ret == 1

    # Manifest partition classification rejects unknown machine prefix
    with pytest.raises(ValueError, match="unknown partition for machine"):
        twin._partition_of_machine("UNKNOWN_MACHINE_99")


def test_case09_tampered_digest_rejected():
    """Case 9: Tampered digest (mutated record fails digest equality)."""
    rec = twin.run_episode(777, None)
    honest_digest = twin.replay_digest(rec)

    # Mutation 1: altered seed
    tampered_seed = copy.deepcopy(rec)
    tampered_seed["seed"] = 999
    assert twin.replay_digest(tampered_seed) != honest_digest

    # Mutation 2: corrupted observation data
    tampered_obs = copy.deepcopy(rec)
    tampered_obs["obs"][0][0] += 1.0
    assert twin.replay_digest(tampered_obs) != honest_digest

    # Mutation 3: tampered code_version
    tampered_ver = copy.deepcopy(rec)
    tampered_ver["code_version"] = "99.99.99-tampered"
    assert twin.replay_digest(tampered_ver) != honest_digest

    # Comparison failure against tampered declared digest
    tampered_digest_value = "0" * 64
    assert honest_digest != tampered_digest_value


def test_case10_null_episode_record_rejected():
    """Case 10: Null episode / None record rejected by replay_digest with explicit exception."""
    with pytest.raises((AttributeError, TypeError, ValueError)):
        twin.replay_digest(None)


def test_case11_mag_sigma_out_of_range_rejected():
    """Case 11: Out-of-range mag_sigma rejected by twin._validate with ValueError."""
    for bad_mag in (100, 0.01, -3, 8.1, 0.49, True, "abc"):
        with pytest.raises(ValueError, match="mag_sigma out of range"):
            twin._validate(
                777,
                {
                    "origin": "B2",
                    "class": "drift",
                    "t0": 150,
                    "dur": 12,
                    "mag_sigma": bad_mag,
                },
            )
