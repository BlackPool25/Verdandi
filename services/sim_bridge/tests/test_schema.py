"""T3 schema-lock tests (failing-first, TDD red).

Locks the frozen tick contract: no `temperature` key anywhere, quality
only as sparse parts[]-last join, c7tail episode-final only, throughput
domain {0,1}, 7 event families with {event,t,machine,detail} base shape
and natural/gt_excluded/fault_id top-level ONLY on DOWN/UP.

Validates 3 seeds (7, 777, 1234) end-to-end from src.twin.run_episode
through services.sim_bridge.schema.build_tick + validate_tick.
"""

import copy

import pytest

from services.sim_bridge import schema as S
from src.config import BUFFERS
from src.twin import run_episode

SEEDS = [7, 777, 1234]


def good_tick(seed=7):
    rec = run_episode(seed, None)
    return S.build_tick(rec, 0), rec


def test_no_temperature_key_in_tick():
    tick, _ = good_tick()
    assert "temperature" not in tick
    assert "temp" not in tick


def test_tick_keys_frozen():
    tick, _ = good_tick()
    assert set(tick.keys()) == set(S.TICK_KEYS), f"extra={set(tick) - set(S.TICK_KEYS)}"


def test_flag_source_sparse_join():
    tick, rec = good_tick()
    q = tick["quality"]
    for entry in q.values():
        if entry == S.NO_PART_YET:
            continue
        assert entry["source"] in S.FLAG_SOURCES
        assert entry["source"] == "parts-last"
        assert entry["flag"] in S.FLAG_VALUES
        assert "part_id" in entry
    # cross-check: machine with a delivered part must cite that part
    last = S.quality_for_machine(rec["parts"], "A0")
    assert q["A0"] == last


def test_no_held_flag_claim():
    tick, _ = good_tick()
    for machine, entry in tick["quality"].items():
        if entry == S.NO_PART_YET:
            continue
        assert entry["flag"] in ("OK", "DEGRADE", "REJECT"), machine


def test_c7tail_final_only():
    tick, rec = good_tick()
    assert "c7tail" not in tick and "c7tail_final" not in tick
    header = S.build_header(rec)
    assert "c7tail_final" in header
    assert header["c7tail_final"] == rec["flow_stats"]["c7tail"]
    assert S.C7TAIL_SERIES_WAIVER.startswith("no per-step series")


def test_throughput_domain_01():
    for seed in SEEDS:
        rec = run_episode(seed, None)
        for k in (0, 150, 299):
            tick = S.build_tick(rec, k)
            for v in tick["throughput"]:
                assert v in S.THROUGHPUT_DOMAIN, f"seed={seed} k={k} tput={v!r}"
            S.validate_tick(tick)


def test_event_allowlist_7_families():
    assert len(S.EVENT_FAMILIES) == 7
    for seed in SEEDS:
        rec = run_episode(seed, None)
        for k in (0, 150, 299):
            tick = S.build_tick(rec, k)
            for ev in tick["events_at_k"]:
                assert {"event", "t", "machine", "detail"} <= set(ev.keys())
                fam = S.event_family(ev["event"])
                assert fam in S.EVENT_FAMILIES
                if ev["event"] in ("DOWN", "UP"):
                    for key in ("natural", "gt_excluded", "fault_id"):
                        assert key in ev, f"{ev['event']} missing top-level {key}"
                else:
                    for key in ("natural", "gt_excluded", "fault_id"):
                        assert key not in ev, f"{ev['event']} must not carry {key}"


def test_buffers_0_cap_and_sbuf_level():
    tick, _rec = good_tick()
    sbuf_idx = list(BUFFERS).index("SBUF")
    assert tick["sbuf_level"] == tick["buffers"][sbuf_idx]
    for lvl, (name, cap) in zip(tick["buffers"], BUFFERS.items()):
        assert 0 <= lvl <= cap, f"{name} level={lvl} cap={cap}"


def test_three_seeds_validate():
    for seed in SEEDS:
        rec = run_episode(seed, None)
        for k in (0, 150, 299):
            S.validate_tick(S.build_tick(rec, k))
        S.validate_header(S.build_header(rec))


def test_temp_injected_tick_rejected_loudly():
    tick, _ = good_tick()
    bad = copy.deepcopy(tick)
    bad["temperature"] = 21.5
    with pytest.raises(S.SchemaViolation, match="[Tt]emperature"):
        S.validate_tick(bad)


def test_tput_2_rejected_loudly():
    tick, _ = good_tick()
    bad = copy.deepcopy(tick)
    bad["throughput"] = list(bad["throughput"])
    bad["throughput"][0] = 2
    with pytest.raises(S.SchemaViolation, match="[Tt]hroughput"):
        S.validate_tick(bad)


def test_unknown_event_family_rejected_loudly():
    tick, _ = good_tick()
    bad = copy.deepcopy(tick)
    bad["events_at_k"] = [
        {"event": "OVERHEAT", "t": 0, "machine": "A0", "detail": {}}
    ]
    with pytest.raises(S.SchemaViolation, match="[Ee]vent"):
        S.validate_tick(bad)
