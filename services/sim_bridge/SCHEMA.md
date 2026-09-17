# sim_bridge frozen tick schema v2 (T3 contract lock, topology-A only)

Twin-mirror verbatim; bridge-strict labeled. This document freezes the
tick JSON the bridge replays and the frontend consumes. `GET /schema`
returns the same contract as JSON (`services/sim_bridge/schema.py`
`FROZEN_SCHEMA`). v1 32-machine ticks are rejected with
`schema v1 non-comparable, rebaseline` (v1 digests flow 962b9c54d022 /
demo d2b4fb23… retired, never compared).

## Tick keys (frozen)

`step, states[26], obs[26], throughput[26], buffers[26], sbuf_level,
events_at_k[], faults[], quality{}`. No other keys. In particular there
is **no `temperature` key** (temp gap waiver below).

## Waivers

- **Temp gap:** the twin discards `_temp` from `_sample_signal`
  (`val, _temp, ar = ...`, `src/twin.py:602,764,892,1010`). The bridge
  never invents it; any tick carrying `temperature`/`temp` is rejected
  by `validate_tick`.
- **Quality gap:** the quality flag rides the part object downstream
  (`src/twin.py:595-598,735-741,628-638`), never a per-tick-per-machine
  channel, and `held` is never returned by the twin. Panels show only
  the sparse join `{source:"parts-last", flag, part_id}` per machine
  (last `parts[]` delivery for that machine) or
  `"no completed part yet"`. No per-tick-per-machine held-flag claim.
- **Throughput 0/1 vs SIM_SPEC:** the twin emits `st, tput = "RUN", 1`
  else `0` (`src/twin.py:753`), including ASM0. This contradicts the
  SIM_SPEC §8 `(0-3 ASM0 kit)` parenthetical — **the twin wins** for
  display. Domain is `{0,1}`; `validate_tick` rejects anything else.
- **c7tail final-only:** the twin emits `_C7TAIL` only as an
  episode-final store census (`flow_stats.c7tail`/`store_final`,
  `src/twin.py:1063-1065,1137-1138,1168-1172`). No 300-step series
  exists. The header carries `c7tail_final`; the topology node shows
  the final plus a "no per-step series" label. The bridge MAY
  reconstruct a derived series from AGV `parts[]` delivery events only
  if labeled `provenance:"derived"` — this bridge does not (the single
  final value suffices for the topology node), so no derived series is
  emitted.

## Buffers

26 roster buffers, each level in `0-cap`. `sbuf_level` is extracted from
`buffers[SBUF]` (must equal it; `validate_tick` asserts this).

## Events

Base shape `{event, t, machine, detail}` for ALL variants. The trio
`natural`/`gt_excluded`/`fault_id` appears top-level ONLY on DOWN/UP
(`src/twin.py:409-454`): `fault_id` set means injected (inside a GT
window), `None` means natural (`natural:true, gt_excluded:true`).
Seven families: FAULT (`FAULT_START`/`END`), BLOCK (`BLOCK_ON`/`OFF`),
STARVE (`STARVE_ON`/`OFF`), DOWN_UP (`DOWN`/`UP`), `AGV_WAIT`,
`REJECT_ROUTE`, `DIVERT_SBUF` — plus the topology-A trio, each its own
family: `FAILOVER` (B-pair reroute, top-level `from`/`to`/`reason`),
`PACK_FORK` (PKG0 split, detail `part`/`to`), `LATE_VERDICT` (INSP0
release, detail `part`/`verdict`). Ten families total (7R: the 6R TAKT5
retime raised trio volume onto sampled ticks, exposing the 7-family gap).

## Episode header (once per episode, NOT per tick)

`seed, T, sbuf_stats, flow_stats, c7tail_final` (full finals live here).
