"""STARVED-split census + digest scrub (topology-A port of upstream D1).

Upstream (32-machine, commit 8e0566b): post-hoc STARVED census nested under
flow_stats["starved_split"] (state-row counting, no condition/RNG/draw
change) + _DIGEST_SCRUB_FLOW_KEYS scrub in replay_digest so same-seed
digests stay bit-identical. Triage: drain (D2), round-robin (D3b), and pins
already exist on topology-A — deliberately NOT re-ported here.

26-roster taxonomy (re-derived from src/twin.py, NOT copied 32-machine
literals — PKG0/1/2, INSP0, B7P/B7S did not exist upstream):
- feed_wait: STARVED cells over _LINES (22 machines: A/B/C survivors +
  B7P/B7S pair + PKG0/PKG1/PKG2 + INSP0). Heads A0/B0/C0 never STARVE
  (up=None spawn); every other line STARVE fires only when the immediate
  upstream gap is empty (single: len==0; B8 join: first-non-empty none),
  so each such step is an upstream-gap wait by construction.
- kit_miss_A/B/C: ASM0 STARVED steps joined per-step to the kit-emptiness
  snapshot logged by _asm0_process (kit_missing emits on STARVED-entry
  only, so transition events undercount — the per-step join is the point).
  Multi-empty steps attribute A>B>C priority so A+B+C == ASM0 STARVED.
- cell_wait: ASM1 (up ASM01) + ASM2 (up INSP02) STARVED on empty intake.
- rwk_idle: RWK0 STARVED on empty RWK_RET intake.
Buckets partition every STARVED cell, hence sum EXACTLY to raw STARVED.

Digest contract: replay_digest scrubs flow_stats sub-dicts in
twin._DIGEST_SCRUB_FLOW_KEYS — reruns stay identical AND old records
without the key hash exactly as before. Existing golden pins (777-clean
652fba4f…, 777 F-21 523b0b9e… == services/sim_bridge/golden/
replay-777-topology-A.json) MUST NOT move.
"""

import copy

import pytest

from src import twin
from src.config import MACHINE_INDEX, T

pytestmark = pytest.mark.k2

_SEEDS = (777, 42)

_F21_B2 = {
    "id": "F-21",
    "class": "drift",
    "origin": "B2",
    "t0": 150,
    "dur": 12,
    "mag_sigma": 5.2,
}

_DIGEST_CLEAN777 = (
    "652fba4f5f5f2e92cda0d1d71ee1be081731d1c638cf48f05dec9eac9cb5458b"
)
_DIGEST_F21_777 = (
    "523b0b9e71f47d355cf4e4f4b7f73d29c333747d253d3b016c1edf2957bbd8c4"
)


def _raw_starved(rec):
    st = rec["states"]
    return sum(1 for m in range(len(st)) for t in range(T) if st[m][t] == "STARVED")


def _asm0_starved(rec):
    row = rec["states"][MACHINE_INDEX["ASM0"]]
    return sum(1 for t in range(T) if row[t] == "STARVED")


@pytest.mark.parametrize("seed", _SEEDS)
def test_split_buckets_sum_to_raw_starved(seed):
    rec = twin.run_episode(seed, None)
    split = rec["flow_stats"]["starved_split"]
    buckets = (
        split["feed_wait"]
        + split["kit_miss_A"]
        + split["kit_miss_B"]
        + split["kit_miss_C"]
        + split["cell_wait"]
        + split["rwk_idle"]
    )
    assert buckets == _raw_starved(rec) == split["raw_starved"]
    # KIT-by-line roll-up + ASM0 identity: every ASM0 STARVED step lands
    # in exactly one KIT bucket.
    assert split["kit_miss"] == (
        split["kit_miss_A"] + split["kit_miss_B"] + split["kit_miss_C"]
    )
    assert split["kit_miss"] == _asm0_starved(rec)


@pytest.mark.parametrize("seed", _SEEDS)
def test_split_fault_episode_still_partitions(seed):
    rec = twin.run_episode(seed, copy.deepcopy(_F21_B2))
    split = rec["flow_stats"]["starved_split"]
    assert (
        split["feed_wait"]
        + split["kit_miss_A"]
        + split["kit_miss_B"]
        + split["kit_miss_C"]
        + split["cell_wait"]
        + split["rwk_idle"]
        == _raw_starved(rec)
    )


def test_digest_ignores_split_key():
    r1 = twin.run_episode(777, None)
    r2 = twin.run_episode(777, None)
    assert twin.replay_digest(r1) == twin.replay_digest(r2)  # rerun-identical
    stripped = copy.deepcopy(r1)
    del stripped["flow_stats"]["starved_split"]
    assert twin.replay_digest(r1) == twin.replay_digest(stripped)  # old-records-hash-same


def test_golden_digests_unmoved():
    assert twin.replay_digest(twin.run_episode(777, None)) == _DIGEST_CLEAN777
    f1 = twin.run_episode(777, copy.deepcopy(_F21_B2))
    assert twin.replay_digest(f1) == _DIGEST_F21_777
