# Frontend — /sim twin viewer

Live view of one factory episode: topology, machine panels, playback
controls, event feed with the anomaly overlay, and a Canvas telemetry
strip. Backend contract:
[services/sim_bridge/SCHEMA.md](../services/sim_bridge/SCHEMA.md).
Twin reference: [src/twin.py](../src/twin.py).
Spec context: [SIM_SPEC.md](SIM_SPEC.md).
Demo: [demo/frontend.sh](../demo/frontend.sh).

## Architecture

```
bridge :8000                     browser /sim
─────────────────                ─────────────────────────────
POST /episode ──► episode_id ──► SimPage auto-seeds ?seed= (777)
                                 │  (ControlsBar posts later episodes;
                                 │   ?episode= deep-links a storm episode)
                                 ▼
GET /stream ──SSE──► TickStreamController (single EventSource)
(header + 300 ticks,             │  rows keyed by step, ?from_step resume
 ?from_step resume)              ▼
                     shared playback cursor (play/pause/speed/step)
                       ├── TopologyView (states patch via updateNodeData;
                       │   GT/neighbor/DOWN anomaly via updateNodeData)
                       ├── MachinePanel / BufferBars (PanelTick mapping)
                       ├── MachineGrid (selection only, no stream)
                       ├── StripChart (SBUF-or-selected obs ring; rAF +
                       │   Zustand transient subscribe, badges at 4–10Hz)
                       ├── EventFeed (cursor-following accumulation,
                       │   cap 100 + "…+N more" + family filter)
                       └── ControlsBar[external] (episode + playback UI)
```

One episode, one EventSource, one cursor: panels, topology, charts, feed,
and controls read the same buffered rows, so they never diverge. The dev
harnesses (`controls.html`, `events.html`) keep their own streams and are
not part of the /sim path.

## Tick schema

Frozen contract, 9 keys (see
[SCHEMA.md](../services/sim_bridge/SCHEMA.md)):
`step, states[32], obs[32], throughput[32], buffers[31], sbuf_level,
events_at_k[], faults[], quality{}`. Roster order is Python `sorted()`
(`A0–A9, ASM0–2, B0–B9, C0–C7, RWK0`), exposed as `STREAM_MACHINE_ORDER`.
The episode header carries `seed, T, sbuf_stats, flow_stats,
c7tail_final`, plus the episode digest. There is no `temperature` key.

## Controls

| Control | Effect |
|---|---|
| seed | Episode seed for the next POST /episode (demo: 777) |
| Start new episode | POSTs seed + fault drafts; old stream closes, cursor resets, autoplay resumes |
| Play / Pause | Freezes or resumes the shared cursor (timer cleared on pause) |
| speed (1x/2x/4x) | 1x = 4 steps/s; cursor-only, never reconnects |
| Step −1 / Step +1 | Deterministic step over buffered rows (same step, byte-identical row) |
| enable_natural_breakdown | Twin natural DOWN/UP events on or off for the next episode |
| fault form | class, origin, t0, dur, extra JSON; STUCK normalizes to breakdown; quality outside ASM2 is an accepted no-op (`noop_warning`) |
| cursor / rows / episode / digest | Readouts: `Step k / 300`, buffered row count, episode id, episode digest |
| validation hints | t0 ≥ 120 · t0+dur ≤ 300 · same-machine gap ≥ 5 · dur 8–25 · mag 4–7σ · delay d 3–6 · drop 0.10–0.30 · mttr_mult 1–3 · reject 0.15–0.40 |

Failed submits (e.g. t0=119, twin text "fault window out of range") render
inline with the old episode and stream intact.

## Episodes and digest

`POST /episode` precomputes one episode and returns an `episode_id` plus an
episode digest. Same seed + same faults give the same digest across POSTs
(new id each time, no stale reuse); concurrent fault POSTs start a new
episode and the old stream is closed. The demo seeds 777 with F-21 (drift,
B5, t0=150, dur=12, mag 5.2); its digest matches
[check_replay.py](../services/sim_bridge/scripts/check_replay.py).
Digest covers the twin record, not the transport envelope. A storm episode
can be deep-linked as `/sim?episode=<id>` (auto-seed is skipped).

## Topology

34 nodes (32 machines + SBUF + `_C7TAIL`) and a pinned 36-edge inventory
(25 line-gap + 3 tail-stage + 4 AGV-drain + 2 assembly + 2 rework, with
`ASM2→RWK0` as the dagre back-edge). Dagre layout runs on topology change
only; nodes are memoized and patched per tick via `updateNodeData`, with
`onlyRenderVisibleElements` for the 32-node field. A snapshot test asserts
no overlap at 2x sprite scale with the rework cycle present.

## Sprites

9 rect-based `crispEdges` SVG symbols (`feed, form, process, finish,
inspect-tail, assembly-kit, assembly-join, test, rework`; `assembly-kit`
and `assembly-join` are distinct by construction) emitted by
`src/sprites/generate.mjs` with same-color rect merging. See Palette below
for the audit.

## Event feed

Global feed accumulates `events_at_k` following the shared cursor (rewinds
rebuild from buffered rows). Rows render latest-first capped at 100 with a
"…+N more" badge counting the hidden older rows, plus a family filter
(`ALL` + 7 families); DOWN/UP rows carry the `! FAULT` / `! NATURAL` glyph
so color is never the only signal. Empty feed renders a one-line empty row.

## Telemetry

One `StripChart` (selected machine, else B5) paints the obs ring on Canvas
via `requestAnimationFrame`: per-tick updates arrive through the Zustand
transient subscribe (refs, never React state), React badges only at
4–10Hz. The render-counter spec proves graph chrome renders 0 times per
tick while Canvas paints every tick (p95 tick-to-paint ≤100ms at 1x,
≤200ms at 4x).

## GT vs DOWN (ruling A)

- GT outline `[t0, t0+dur)` marks the injected fault window on the origin
  machine only (demo: B5 steps 150–162).
- DOWN outlives GT: the extended down window (`downWindowOf`, breakdown
  marker uses the GT end) renders distinctly from the GT outline.
- Natural DOWN/UP (`fault_id: null`) is labeled natural and never takes a
  fault outline, even inside a clean window.
- Depth-1 buffer-neighbor highlight covers same-step BLOCKED/STARVED only
  (AGV-drain edges excluded); B7 never highlights for the F-21 window.
- Every anomaly shows a `!` glyph plus text: color is never the only
  signal. With `prefers-reduced-motion` the overlay is static.

## Quality gap

Quality rides the part object downstream and `held` is never returned, so
there is no per-tick-per-machine channel. Panels show the sparse join
(last `parts[]` delivery per machine) or "no completed part yet".

## Temp gap

The twin discards `_temp`; the bridge never invents it. Any tick carrying
a temperature key is rejected by validation.

## Throughput note

The twin emits throughput in `{0,1}` (RUN → 1 else 0, ASM0 included),
which overrules the SIM_SPEC §8 `(0–3 ASM0 kit)` parenthetical for
display. Anything outside `{0,1}` is rejected.

## Palette

Sprites and status hues are Sweetie16-locked (see the T6 audit); panels
are dark `#111` with a 1px border, Press Start 2P headings on 8px
multiples, VT323 body, integer 2x/4x sprite sizes. The audit script fails
on any off-palette hex.

## Stream lifecycle

Single `EventSource` per /sim mount. Disconnects resume from the cursor
(`?from_step=k`, rows idempotent); speed changes never reconnect; a
completed 300/300 stream never reconnects. Errors flip the shared
`connected` flag during render (no new tick needed), so the
"Bridge disconnected" banner appears live and clears on resume. Measured
episode budget stays under 2MB.

## States

Loading shows a pixel-style skeleton (static blocks on 8px multiples)
until the first rows buffer. A dead bridge at seed time shows an inline
seed error with retry instead of a hang. Feed and chart render explicit
empty captions before the first tick. Unknown `?episode=` ids show the
disconnected banner with the layout intact — no crash. Primary viewport
≥1280, usable at 768 (no horizontal overflow; long row JSON wraps).

## Adversarial limits (accepted substitution)

A 120-seed sweep proved SBUF high-util (≥24/30) and RWK_RET-full (cap 10)
unreachable live: the AGV drain (2 in service + 2 queued, SBUF-first) and
the RWK0 drain outpace every fault-driven inflow (line-end breakdowns ×3,
sustained quality ×2 at 0.40, delay cascades — SBUF/RWK maxima stay ≤2).
Storm coverage therefore asserts the reachable neighbors: multi-fault
episodes (seed 4242, 603 events), quality-surge REJECT flags on ASM2 (seed
59), delay-cascade DIVERT_SBUF rows (seed 95, 6 rows), feed caps, digest
determinism, and real BLOCKED ticks shown-not-hidden (C4 at step 271).
The SBUF high-util badge stays covered by a synthetic unit case.

## Demo and waiver

`demo/frontend.sh` (idempotent: reuses healthy servers or starts its own)
brings up the bridge, seeds 777 F-21, opens /sim, autoplays 1x, pauses at
t=160, steps to 161, saves a screenshot and a tour video under
`.omo/evidence/task-11-*`, then probes banner-on-kill plus resume. A dead
bridge fails fast with an actionable message (no stack trace).

Waiver: the SSE transport is a demo viewer. The SIM_SPEC live-stream path
stays a non-goal; nothing here claims production streaming semantics.

## Gates (T12) + CI mapping

One invocation (from `frontend/`): `npm run gates` → palette audit,
scope grep, `tsc --noEmit`, full unit vitest, `src/`-untouched check.
Full acceptance (from repo root):

```
npm --prefix frontend run gates && pytest services/sim_bridge/tests -q \
  && ruff check services/ && mypy services/ \
  && pip-audit -r services/sim_bridge/requirements.txt
```

| Gate | Command | Fails when |
|---|---|---|
| palette | `npm run palette-audit` (`src/sprites/audit.mjs`) | any off-palette hex in `sprites.svg` |
| scope | `npm run scope` (`scripts/scope-grep.mjs`) | word-boundary forbidden token (plan line 31) under `frontend/`+`services/`; `replay_digest` allowlisted in `services/` |
| a11y | `src/test/reduced-motion.spec.ts` (+ T9 `anomaly.spec.ts` blink block) | `steps()` blink without `prefers-reduced-motion: reduce` → `animation: none` static outline |
| perf | `src/test/render-counter.spec.ts` (6 tests) | per-tick chrome renders ≠ 0, Canvas paints = 0, p95 > 100ms@1x / 200ms@4x |
| fidelity | `git diff --stat -- src/` empty (gates.sh step 5) | any `src/` edit |
| bridge | `pytest services/sim_bridge/tests -q` + `ruff check services/` + `mypy services/` + `pip-audit -r services/sim_bridge/requirements.txt` | any red (markers in `pytest.ini` unaffected) |

`.github/` is held locally (gitignored until the token gains workflow
scope), so CI wiring lands as `package.json` scripts + this mapping, not
as a workflow edit: the `lint-type` job maps to gates steps 1–3 + the
bridge lint/type row; `battery`/`killbars-security` map to the bridge test
row; `e2e-demo` maps to `demo/frontend.sh`. Do NOT force-push `.github/`.

## Verification status

| Suite | Result |
|---|---|
| vitest (unit) | 61/61, 6 files, 0 failed suites (`npm test`) |
| playwright (e2e) | 25/25: topology 1, panels 5, controls 6, events 8, storms 5 |
| pytest (bridge) | 39/39; `ruff check` + `mypy` + `pip-audit` clean |
| tsc / build | `tsc --noEmit` 0 errors; `vite build` clean |
| Final Wave | F1 plan-compliance APPROVE; F2 quality APPROVE (nits only); F3 manual QA 12/12 APPROVE; F4 scope-fidelity APPROVE |

Known nits (non-blocking): vite chunk-size >500kB warning (code-split
suggestion); Starlette `httpx`-vs-`httpx2` deprecation warning in the test
env; `topology.spec.ts` needs a manually started dev server on :19104.
