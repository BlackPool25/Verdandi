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

// T8 failing-first: panel values must equal the live tick payload for the 3
// probed steps [0,150,299] (seed 777, frozen schema). Fixture holds real
// schema.build_tick rows (read-only run_episode dump, not hand-made).
const PROBED = [0, 150, 299] as const;

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
      const probes: Record<string, string> = {
        feed: "A0", form: "A1", process: "B2", finish: "A8",
        "inspect-tail": "A9", "assembly-kit": "ASM0", "assembly-join": "ASM1",
        test: "ASM2", rework: "RWK0",
      };
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
      expect(bars).toHaveLength(26);
      const raw = tickAt(step);
      for (let j = 0; j < bars.length; j += 1) {
        const bar = bars[j];
        expect(bar?.level).toBe(raw?.buffers[j]);
        expect(bar?.id).toBe(BUFFER_ORDER[j]);
      }
      const sbuf = bars.find((b) => b.id === "SBUF");
      expect(sbuf?.cap).toBe(30);
      expect(sbuf?.level).toBe(raw?.sbuf_level);
      // SBUF cap 30 → high-util ≥80% ⇔ level ≥ 24
      expect(sbuf?.high).toBe((raw?.sbuf_level ?? 0) >= 24);
    });
  }

  it("synthetic SBUF 25/30 → high-util badge on (threshold ≥24)", () => {
    const tick = { ...panelTickAt(150), buffers: [...panelTickAt(150).buffers], sbuf_level: 25 };
    const sbufIdx = BUFFER_ORDER.indexOf("SBUF");
    (tick.buffers as number[])[sbufIdx] = 25;
    const bars = bufferBarsFor(tick);
    const sbuf = bars.find((b) => b.id === "SBUF");
    expect(sbuf?.cap).toBe(30);
    expect(sbuf?.high).toBe(true);
  });

  it("tails ride the AGV path, never SBUF-divert; feed/form never divert", () => {
    for (const tail of ["A9", "B9", "C7"]) {
      expect(tailPathFor(tail)).toBe("AGV");
    }
    expect(tailPathFor("A0")).toBe("never-diverts");
    expect(tailPathFor("B1")).toBe("never-diverts");
    expect(tailPathFor("C1")).toBe("never-diverts");
  });

  it("c7tail panel shows final + no-series label", () => {
    const tick = panelTickAt(299);
    const panel = machinePanelFor(tick, "_C7TAIL");
    expect(panel.found).toBe(true);
    if (!panel.found || panel.kind !== "c7tail") return;
    expect(panel.c7tailFinal).toBe(F.header.c7tail_final);
    expect(panel.noSeriesLabel).toBe("no per-step series");
  });

  it("unknown machine id → empty state, no throw", () => {
    const tick = panelTickAt(150);
    expect(() => machinePanelFor(tick, "ZZZ")).not.toThrow();
    const panel = machinePanelFor(tick, "ZZZ");
    expect(panel.found).toBe(false);
  });

  it("reselect same machine → same values (stale-state guard)", () => {
    const tick = panelTickAt(150);
    const a = machinePanelFor(tick, "B7P");
    const b = machinePanelFor(tick, "B7P");
    expect(a).toEqual(b);
  });
});
