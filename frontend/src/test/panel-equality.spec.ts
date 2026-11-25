import { describe, expect, it } from "vitest";
import fixture from "./fixtures/ticks-A-777.json";
import { toFaultSpec } from "../components/events/anomaly";
import type { FaultSpec } from "../components/events/types";
import {
  bufferBarsFor,
  machinePanelFor,
  tailPathFor,
  type PanelTick,
} from "../components/panels/selectors";
import { MACHINE_META } from "../components/panels/machineMeta";
import { STREAM_MACHINE_ORDER, parseFeedEvents } from "../sim/streamCodec";
import { BUFFER_IDS } from "../store/tick";
import {
  AGV_TAILS,
  C7TAIL_ID,
  CLASS_PROBES,
  FINAL_STEP,
  LIVE_STEP,
  MACHINE_COUNT,
  NEVER_DIVERTS,
  NO_SERIES_LABEL,
  PROBED_STEPS,
  SBUF_CAP,
  SBUF_HIGH_LEVEL,
  SBUF_ID,
  STALE_GUARD_ID,
  UNKNOWN_MACHINE_ID,
} from "./testConstants";

// T8 failing-first: panel values must equal the live tick payload for the 3
// probed steps [0,150,299] (seed 777, frozen schema). Fixture holds real
// schema.build_tick rows (read-only run_episode dump, not hand-made).
const PROBED = PROBED_STEPS;

interface FixtureShape {
  readonly schema_version: number;
  readonly code_version: string;
  readonly header: {
    readonly seed: number;
    readonly T: number;
    readonly c7tail_final: number;
  };
  readonly ticks: ReadonlyArray<{
    readonly step: number;
    readonly states: readonly string[];
    readonly obs: readonly number[];
    readonly throughput: readonly number[];
    readonly buffers: readonly number[];
    readonly sbuf_level: number;
    readonly events_at_k: readonly unknown[];
    readonly faults: ReadonlyArray<Readonly<Record<string, unknown>>>;
    readonly quality: Readonly<Record<string, unknown>>;
    readonly currents: readonly number[];
  }>;
}

const F = fixture as unknown as FixtureShape;

// Header+TICK parity: rows replay in sorted-26 wire order (STREAM_MACHINE_ORDER)
// and twin BUFFERS order (BUFFER_IDS); c7tail_final rides the header.
const MACHINE_ORDER: readonly string[] = STREAM_MACHINE_ORDER;
const BUFFER_ORDER: readonly string[] = BUFFER_IDS;

function tickAt(step: number) {
  const t = F.ticks.find((k) => k.step === step);
  if (t === undefined) throw new Error(`fixture missing step ${step}`);
  return t;
}

function panelTickAt(step: number): PanelTick {
  const t = tickAt(step);
  const faults: FaultSpec[] = [];
  for (const f of t.faults) {
    try {
      faults.push(toFaultSpec(f));
    } catch {
      continue;
    }
  }
  return {
    step: t.step,
    states: t.states,
    obs: t.obs,
    throughput: t.throughput,
    buffers: t.buffers,
    sbuf_level: t.sbuf_level,
    quality: t.quality,
    currents: t.currents,
    events_at_k: parseFeedEvents(t),
    faults,
    machineOrder: MACHINE_ORDER,
    bufferOrder: BUFFER_ORDER,
    c7tailFinal: F.header.c7tail_final,
  };
}

describe("T8 panel equality vs live tick payload", () => {
  for (const step of PROBED) {
    it(`step ${step}: machine panel equals tick payload (state/obs/tput/flag/meta)`, () => {
      // Given: the live tick row at this step + one probe per class
      const tick = panelTickAt(step);
      const probes: Record<string, string> = { ...CLASS_PROBES };
      // When: selecting each class probe
      for (const [cls, id] of Object.entries(probes)) {
        const panel = machinePanelFor(tick, id);
        // Then: panel values are byte-equal to the payload row
        expect(panel.found, `${id} found`).toBe(true);
        if (!panel.found || panel.kind !== "machine") continue;
        const i = MACHINE_ORDER.indexOf(id);
        const raw = tickAt(step);
        expect(raw).toBeDefined();
        expect(panel.state).toBe(raw?.states[i]);
        expect(panel.obs).toBe(raw?.obs[i]);
        expect(panel.tput).toBe(raw?.throughput[i]);
        expect(panel.flag).toEqual(raw?.quality[id] ?? "no completed part yet");
        // meta equals the machines-snapshot row (config Table 3.1)
        const snap = MACHINE_META[id];
        expect(panel.meta.class).toBe(cls);
        expect(panel.meta.base).toBe(snap?.base);
        expect(panel.meta.sigma).toBe(snap?.sigma);
        expect(panel.meta.cycle).toBe(snap?.cycle);
        expect(panel.meta.mttf).toBe(snap?.mttf);
        expect(panel.meta.mttr).toBe(snap?.mttr);
        // envelope note: base±3σ, clamp ±6σ
        const sigma = snap?.sigma ?? 0;
        const base = snap?.base ?? 0;
        expect(panel.envelope.lo3).toBeCloseTo(base - 3 * sigma, 9);
        expect(panel.envelope.hi3).toBeCloseTo(base + 3 * sigma, 9);
        expect(panel.envelope.clampLo6).toBeCloseTo(base - 6 * sigma, 9);
        expect(panel.envelope.clampHi6).toBeCloseTo(base + 6 * sigma, 9);
      }
    });

    it(`step ${step}: buffer bars equal payload (level/cap, SBUF high-util≥24)`, () => {
      // Given: the live tick row
      const tick = panelTickAt(step);
      // When: building buffer bars
      const bars = bufferBarsFor(tick);
      // Then: 26 bars, levels equal payload, caps from BUFFERS
      expect(bars).toHaveLength(MACHINE_COUNT);
      const raw = tickAt(step);
      for (let j = 0; j < bars.length; j += 1) {
        const bar = bars[j];
        expect(bar?.level).toBe(raw?.buffers[j]);
        expect(bar?.id).toBe(BUFFER_ORDER[j]);
      }
      const sbuf = bars.find((b) => b.id === SBUF_ID);
      expect(sbuf?.cap).toBe(SBUF_CAP);
      expect(sbuf?.level).toBe(raw?.sbuf_level);
      // SBUF cap 30 → high-util ≥80% ⇔ level ≥ 24
      expect(sbuf?.high).toBe((raw?.sbuf_level ?? 0) >= SBUF_HIGH_LEVEL);
    });
  }

  it(`synthetic SBUF 25/${SBUF_CAP} → high-util badge on (threshold ≥${SBUF_HIGH_LEVEL})`, () => {
    const tick = { ...panelTickAt(LIVE_STEP), buffers: [...panelTickAt(LIVE_STEP).buffers], sbuf_level: 25 };
    const sbufIdx = BUFFER_ORDER.indexOf(SBUF_ID);
    (tick.buffers as number[])[sbufIdx] = 25;
    const bars = bufferBarsFor(tick);
    const sbuf = bars.find((b) => b.id === SBUF_ID);
    expect(sbuf?.cap).toBe(SBUF_CAP);
    expect(sbuf?.high).toBe(true);
  });

  it("tails ride the AGV path, never SBUF-divert; feed/form never divert", () => {
    for (const tail of AGV_TAILS) {
      expect(tailPathFor(tail)).toBe("AGV");
    }
    for (const feed of NEVER_DIVERTS) {
      expect(tailPathFor(feed)).toBe("never-diverts");
    }
  });

  it("c7tail panel shows final + no-series label", () => {
    const tick = panelTickAt(FINAL_STEP);
    const panel = machinePanelFor(tick, C7TAIL_ID);
    expect(panel.found).toBe(true);
    if (!panel.found || panel.kind !== "c7tail") return;
    expect(panel.c7tailFinal).toBe(F.header.c7tail_final);
    expect(panel.noSeriesLabel).toBe(NO_SERIES_LABEL);
  });

  it("unknown machine id → empty state, no throw", () => {
    const tick = panelTickAt(LIVE_STEP);
    expect(() => machinePanelFor(tick, UNKNOWN_MACHINE_ID)).not.toThrow();
    const panel = machinePanelFor(tick, UNKNOWN_MACHINE_ID);
    expect(panel.found).toBe(false);
  });

  it("reselect same machine → same values (stale-state guard)", () => {
    const tick = panelTickAt(LIVE_STEP);
    const a = machinePanelFor(tick, STALE_GUARD_ID);
    const b = machinePanelFor(tick, STALE_GUARD_ID);
    expect(a).toEqual(b);
  });
});
