"""T3 frozen tick schema v4 (contract lock, cross-team reuse) — topology-A only.

Twin-mirror verbatim; bridge-strict labeled. Locks the tick JSON the
bridge replays (T2) and the frontend consumes (T4+):

- v4-only: N_MACHINES=26 / N_BUFFERS=26 (topology-A roster) + TICK
  `currents` row (CH8 motor-current index, twin _record_current) +
  header `energy` dict (CH9 apparent-energy index, twin _energy_header,
  header-only, never per-tick) + `strat` block (stratification keys,
  funnel census, warm-up pool). Any v1 32-machine tick
  (states/obs/throughput len 32, buffers len 31) is
  strict-rejected with 'schema v1 non-comparable, rebaseline' — the v1
  code path is DELETED except this error. Any v2 record (no
  currents/energy keys) or v3 pre-union record (missing currents or
  strat) is likewise rejected non-comparable via the
  missing-keys path.
- V1_NON_COMPARABLE digests (never asserted equal): flow 962b9c54d022,
  demo d2b4fb23… (32-machine schema v1 baselines, retired).
- NO `temperature` key: src/twin.py discards `_temp` from
  `_sample_signal` (`val, _temp, ar = ...` at lines 602/764/892/1010).
  The twin never emits it, so the bridge must never invent it.
- Quality ONLY as sparse parts[]-last join: the flag rides the part
  object downstream (twin lines 595-598/735-741/628-638), never a
  per-tick-per-machine channel. `held` is never returned by the twin,
  so no per-tick-per-machine held-flag claim exists.
- `c7tail` episode-final only: the twin emits `_C7TAIL` only as a final
  store census (`flow_stats.c7tail`/`store_final`, twin lines
  1063-1065/1137-1138/1168-1172). No 300-step series exists.
- Throughput domain {0,1}: the twin emits `st, tput = "RUN", 1` else 0
  (twin line 753), including ASM0. This contradicts the SIM_SPEC
  §8 `(0-3 ASM0 kit)` parenthetical — the twin wins for display.
- Buffers 0-cap; `sbuf_level` extracted from buffers[SBUF].
- Events: base shape {event,t,machine,detail} for ALL variants, with
  `natural`/`gt_excluded`/`fault_id` top-level ONLY on DOWN/UP
  (twin lines 409-454).
"""

from __future__ import annotations

import math
from typing import Any

from src.config import BUFFERS, CODE_VERSION, N_BUFFERS, N_MACHINES, TWIN_SCHEMA

SCHEMA_VERSION = TWIN_SCHEMA  # topology-A; must equal src.config.TWIN_SCHEMA
assert SCHEMA_VERSION == TWIN_SCHEMA
assert SCHEMA_VERSION in (4, 5)

V1_REJECT_MSG = "schema v1 non-comparable, rebaseline"

# V1_NON_COMPARABLE digests (schema v1, 32-machine; retired, never equal):
# flow 962b9c54d022, demo d2b4fb23… .

TICK_KEYS = (
    "step",
    "states",
    "obs",
    "throughput",
    "buffers",
    "sbuf_level",
    "events_at_k",
    "faults",
    "quality",
    "currents",
)

HEADER_KEYS = ("seed", "T", "sbuf_stats", "flow_stats", "c7tail_final", "energy")

FLAG_SOURCES = ("parts-last",)
FLAG_VALUES = ("OK", "DEGRADE", "REJECT")
NO_PART_YET = "no completed part yet"

THROUGHPUT_DOMAIN = frozenset({0, 1})

EVENT_FAMILIES = (
    "FAULT",
    "BLOCK",
    "STARVE",
    "DOWN_UP",
    "AGV_WAIT",
    "REJECT_ROUTE",
    "DIVERT_SBUF",
    # Topology-A trio (Todo 3 normative taxonomy, twin _emit; 7R: the 6R
    # TAKT5 retime raised per-episode PACK_FORK/LATE_VERDICT volume so
    # sampled ticks (0/150/299) now carry them — the 7-family allowlist
    # rejected live twin ticks; each trio event is its own family).
    "FAILOVER",
    "PACK_FORK",
    "LATE_VERDICT",
)

_EVENT_TO_FAMILY = {
    "FAULT_START": "FAULT",
    "FAULT_END": "FAULT",
    "BLOCK_ON": "BLOCK",
    "BLOCK_OFF": "BLOCK",
    "STARVE_ON": "STARVE",
    "STARVE_OFF": "STARVE",
    "DOWN": "DOWN_UP",
    "UP": "DOWN_UP",
    "AGV_WAIT": "AGV_WAIT",
    "REJECT_ROUTE": "REJECT_ROUTE",
    "DIVERT_SBUF": "DIVERT_SBUF",
    "FAILOVER": "FAILOVER",
    "PACK_FORK": "PACK_FORK",
    "LATE_VERDICT": "LATE_VERDICT",
}

DOWN_UP_TRIPLE = ("natural", "gt_excluded", "fault_id")

C7TAIL_SERIES_WAIVER = (
    "no per-step series: the twin emits _C7TAIL only as an episode-final "
    "store census (flow_stats.c7tail / store_final). The topology node "
    "shows the final plus this label. The bridge MAY additionally "
    "reconstruct a derived series from AGV parts[] delivery events only "
    "if labeled provenance:'derived'; this bridge does not reconstruct "
    "one (single final value is sufficient for the T4 topology node), "
    "so no derived series is emitted."
)

TPUT_WAIVER = (
    "twin wins: the twin emits throughput 0/1 on every machine including "
    "ASM0 (twin line 753), contradicting the SIM_SPEC section 8 "
    "'(0-3 ASM0 kit)' parenthetical. Display domain is {0,1}."
)


class SchemaViolation(ValueError):
    """Loud rejection of any tick/header/event breaking the frozen schema."""


def event_family(name: str) -> str:
    """Map an event name to its family; raise on unknown names."""
    try:
        return _EVENT_TO_FAMILY[name]
    except KeyError:
        raise SchemaViolation(
            f"unknown event family for event={name!r}; "
            f"allowlist={sorted(_EVENT_TO_FAMILY)}"
        ) from None


def quality_for_machine(
    parts: list[dict[str, Any]], machine: str
) -> dict[str, Any] | str:
    """Sparse join: last-completed-part flag for one machine.

    Reads parts[] delivery events (each carries the flag that rode the
    part downstream) and returns the most recent entry for `machine` as
    {source:"parts-last", flag, part_id}, or "no completed part yet".
    """
    for p in reversed(parts):
        if p.get("machine") == machine:
            return {
                "source": "parts-last",
                "flag": p.get("flag", "OK"),
                "part_id": p.get("id"),
            }
    return NO_PART_YET


def _machines(record: dict[str, Any]) -> list[str]:
    return sorted(record["machines"])


def build_tick(record: dict[str, Any], k: int) -> dict[str, Any]:
    """Build frozen-schema tick k from a run_episode record (no temp)."""
    order = _machines(record)
    idx = {m: i for i, m in enumerate(order)}
    sbuf_idx = list(BUFFERS).index("SBUF")
    states = [record["states"][idx[m]][k] for m in order]
    obs = [record["obs"][idx[m]][k] for m in order]
    tput = [record["throughput"][idx[m]][k] for m in order]
    bufs = [record["buffers"][j][k] for j in range(len(BUFFERS))]
    events = [e for e in record["events"] if e.get("t") == k]
    quality = {m: quality_for_machine(record["parts"], m) for m in order}
    currents = [record["currents"][idx[m]][k] for m in order]
    return {
        "step": k,
        "states": states,
        "obs": obs,
        "throughput": tput,
        "buffers": bufs,
        "sbuf_level": bufs[sbuf_idx],
        "events_at_k": events,
        "faults": record["faults"],
        "quality": quality,
        "currents": currents,
    }


def build_header(record: dict[str, Any]) -> dict[str, Any]:
    """Build the episode header (once per episode, NOT per tick)."""
    return {
        "seed": record["seed"],
        "T": record["T"],
        "sbuf_stats": record["sbuf_stats"],
        "flow_stats": record["flow_stats"],
        "c7tail_final": record["flow_stats"]["c7tail"],
        "energy": record["flow_stats"]["energy"],
    }


def validate_event(ev: dict[str, Any]) -> None:
    """Validate one event dict against the frozen event contract."""
    for key in ("event", "t", "machine", "detail"):
        if key not in ev:
            raise SchemaViolation(f"event missing base key {key!r}: {ev!r}")
    fam = event_family(ev["event"])
    if fam == "DOWN_UP":
        for key in DOWN_UP_TRIPLE:
            if key not in ev:
                raise SchemaViolation(
                    f"{ev['event']} missing top-level {key!r}: {ev!r}"
                )
    else:
        for key in DOWN_UP_TRIPLE:
            if key in ev:
                raise SchemaViolation(
                    f"{ev['event']} must not carry top-level {key!r}: {ev!r}"
                )


def validate_tick(tick: dict[str, Any]) -> None:
    """Validate one tick; reject loudly on any contract break."""
    n_states = len(tick.get("states", []))
    n_obs = len(tick.get("obs", []))
    n_tput = len(tick.get("throughput", []))
    n_bufs = len(tick.get("buffers", []))
    if (n_states, n_obs, n_tput, n_bufs) == (32, 32, 32, 31):
        raise SchemaViolation(V1_REJECT_MSG)
    if (n_states, n_obs, n_tput) != (N_MACHINES, N_MACHINES, N_MACHINES):
        raise SchemaViolation(
            f"{V1_REJECT_MSG}: want {N_MACHINES}/{N_MACHINES}/{N_MACHINES} "
            f"states/obs/throughput, got {n_states}/{n_obs}/{n_tput}"
        )
    if n_bufs != N_BUFFERS:
        raise SchemaViolation(
            f"{V1_REJECT_MSG}: want {N_BUFFERS} buffers, got {n_bufs}"
        )
    if "temperature" in tick or "temp" in tick:
        raise SchemaViolation(
            "tick must not carry a temperature key "
            "(twin discards _temp; see schema.py docstring)"
        )
    extra = set(tick) - set(TICK_KEYS)
    if extra:
        raise SchemaViolation(f"tick has unknown keys: {sorted(extra)}")
    missing = set(TICK_KEYS) - set(tick)
    if missing:
        raise SchemaViolation(f"tick missing keys: {sorted(missing)}")
    for v in tick["throughput"]:
        if v not in THROUGHPUT_DOMAIN:
            raise SchemaViolation(
                f"throughput value {v!r} outside domain "
                f"{sorted(THROUGHPUT_DOMAIN)} ({TPUT_WAIVER})"
            )
    currents = tick.get("currents", None)
    if not isinstance(currents, list) or len(currents) != N_MACHINES:
        got = len(currents) if isinstance(currents, list) else type(currents).__name__
        raise SchemaViolation(
            f"tick currents must be a {N_MACHINES}-row list, got {got!r}"
        )
    for i, v in enumerate(currents):
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            raise SchemaViolation(f"currents[{i}] must be a number: {v!r}")
        if not math.isfinite(v) or v < 0.0:
            raise SchemaViolation(
                f"currents[{i}] value {v!r} outside range [0, inf) "
                "(CH8 hook clamps at 0.0)"
            )
    sbuf_idx = list(BUFFERS).index("SBUF")
    if tick["sbuf_level"] != tick["buffers"][sbuf_idx]:
        raise SchemaViolation("sbuf_level must equal buffers[SBUF]")
    for lvl, (name, cap) in zip(tick["buffers"], BUFFERS.items()):
        if not 0 <= lvl <= cap:
            raise SchemaViolation(
                f"buffer {name} level={lvl} outside 0-cap (cap={cap})"
            )
    for ev in tick["events_at_k"]:
        validate_event(ev)
    for machine, entry in tick["quality"].items():
        if entry == NO_PART_YET:
            continue
        if not isinstance(entry, dict) or entry.get("source") not in FLAG_SOURCES:
            raise SchemaViolation(
                f"quality[{machine}] must be a parts-last join or "
                f"{NO_PART_YET!r}: {entry!r}"
            )
        if entry.get("flag") not in FLAG_VALUES:
            raise SchemaViolation(
                f"quality[{machine}] flag {entry.get('flag')!r} outside {FLAG_VALUES}"
            )
        if "part_id" not in entry:
            raise SchemaViolation(f"quality[{machine}] missing part_id: {entry!r}")


def validate_header(header: dict[str, Any]) -> None:
    """Validate the episode header (c7tail final-only lives here)."""
    extra = set(header) - set(HEADER_KEYS)
    if extra:
        raise SchemaViolation(f"header has unknown keys: {sorted(extra)}")
    missing = set(HEADER_KEYS) - set(header)
    if missing:
        raise SchemaViolation(f"header missing keys: {sorted(missing)}")
    if "c7tail" in header and "c7tail_final" not in header:
        raise SchemaViolation("c7tail must be exposed as c7tail_final only")
    if not isinstance(header["c7tail_final"], int):
        raise SchemaViolation(
            f"c7tail_final must be an int final count: {header['c7tail_final']!r}"
        )
    energy = header["energy"]
    if not isinstance(energy, dict):
        raise SchemaViolation(f"header energy must be a dict: {energy!r}")
    if "sum_kVAh" not in energy or "unit" not in energy:
        raise SchemaViolation(f"header energy missing sum_kVAh/unit: {sorted(energy)}")
    if energy["unit"] != "kVAh-apparent":
        raise SchemaViolation(
            f"header energy unit must be 'kVAh-apparent': {energy['unit']!r}"
        )
    e_sum = energy["sum_kVAh"]
    if isinstance(e_sum, bool) or not isinstance(e_sum, (int, float)):
        raise SchemaViolation(f"header energy sum_kVAh must be a number: {e_sum!r}")
    if not math.isfinite(e_sum) or e_sum < 0.0:
        raise SchemaViolation(
            f"header energy sum_kVAh {e_sum!r} outside range [0, inf)"
        )


FROZEN_SCHEMA: dict[str, Any] = {
    "schema_version": SCHEMA_VERSION,
    "code_version": CODE_VERSION,
    "tick_keys": list(TICK_KEYS),
    "header_keys": list(HEADER_KEYS),
    "excluded_channel_2": "thermal signal absent by contract "
    "(twin discards _temp; validate_tick rejects temp keys)",
    "quality": {
        "mode": "sparse parts[]-last join",
        "entry": '{source:"parts-last", flag, part_id}',
        "empty": NO_PART_YET,
        "flag_sources": list(FLAG_SOURCES),
        "flag_values": list(FLAG_VALUES),
    },
    "c7tail": {
        "mode": "episode-final only",
        "key": "c7tail_final",
        "waiver": C7TAIL_SERIES_WAIVER,
    },
    "currents": {
        "mode": "per-tick row, 26 machines, same order as states",
        "key": "currents",
        "range": "[0, inf) per machine, clamped at 0.0 by the CH8 hook",
    },
    "energy": {
        "mode": "header-only dict, verbatim from flow_stats",
        "key": "energy",
        "unit": "kVAh-apparent",
    },
    "throughput_domain": sorted(THROUGHPUT_DOMAIN),
    "throughput_waiver": TPUT_WAIVER,
    "buffers": {"rule": "0-cap", "sbuf_level": "buffers[SBUF]", "count": N_BUFFERS},
    "machines": {"count": N_MACHINES},
    "v1_reject": V1_REJECT_MSG,
    "events": {
        "base_shape": ["event", "t", "machine", "detail"],
        "families": list(EVENT_FAMILIES),
        "down_up_triple_top_level_only": list(DOWN_UP_TRIPLE),
    },
}
