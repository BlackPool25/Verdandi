import { describe, expect, it } from "vitest";
import fixture from "../../test/fixtures/ticks-777.json";
import { FACEPLATE_IDS } from "./MachinePanel";
import {
  machinePanelFor,
  sbufPanelFor,
  tailPathFor,
  type PanelTick,
} from "./selectors";
import { SBUF_CAP, SBUF_HIGH } from "./machineMeta";

// L4 faceplate rail: the 9 class probes resolve against the live tick row
// with verbatim config sections; SBUF/_C7TAIL specials stay honest.
const EXPECTED_IDS = ["A0", "A2", "A8", "A9", "B5", "C7", "ASM1", "ASM2", "RWK0"];

interface FixtureShape {
  readonly machine_order: readonly string[];
  readonly buffer_order: readonly string[];
  readonly ticks: Readonly<Record<string, {
    readonly step: number;
    readonly states: readonly string[];
    readonly obs: readonly number[];
    readonly throughput: readonly number[];
    readonly buffers: readonly number[];
    readonly sbuf_level: number;
    readonly quality: Readonly<Record<string, unknown>>;
  }>>;
  readonly c7tail_final: number;
}

const F = fixture as unknown as FixtureShape;

function panelTickAt(step: number): PanelTick {
  const t = F.ticks[String(step)];
  if (t === undefined) throw new Error(`fixture missing step ${step}`);
  return {
    step: t.step,
    states: t.states,
    obs: t.obs,
    throughput: t.throughput,
    buffers: t.buffers,
    sbuf_level: t.sbuf_level,
    quality: t.quality,
    machineOrder: F.machine_order,
    bufferOrder: F.buffer_order,
    c7tailFinal: F.c7tail_final,
  };
}

describe("L4 faceplate rail", () => {
  it("exposes exactly the 9 class-probe ids", () => {
    expect([...FACEPLATE_IDS]).toEqual(EXPECTED_IDS);
  });

  it("each probe resolves live values + verbatim sections at step 150", () => {
    // Given: the live tick row
    const tick = panelTickAt(150);
    // When/Then: every faceplate id renders payload-equal values
    for (const id of FACEPLATE_IDS) {
      const panel = machinePanelFor(tick, id);
      expect(panel.found, `${id} found`).toBe(true);
      if (!panel.found || panel.kind !== "machine") continue;
      const i = F.machine_order.indexOf(id);
      const raw = F.ticks["150"];
      expect(panel.state).toBe(raw?.states[i]);
      expect(panel.obs).toBe(raw?.obs[i]);
      expect(panel.tput).toBe(raw?.throughput[i]);
      expect(panel.flag).toEqual(raw?.quality[id] ?? "no completed part yet");
      expect(panel.tailPath).toBe(tailPathFor(id));
      expect(panel.sections.map((s) => s.heading)).toEqual([
        "class",
        "signal",
        "timing",
        "reliability",
        "buffer & routing",
      ]);
      expect(panel.rawJson).toContain(`"id":"${id}"`);
    }
  });

  it("tails ride AGV, feed never diverts (faceplate routing)", () => {
    expect(tailPathFor("A9")).toBe("AGV");
    expect(tailPathFor("C7")).toBe("AGV");
    expect(tailPathFor("A0")).toBe("never-diverts");
    expect(tailPathFor("B5")).toBe("SBUF-eligible");
    expect(tailPathFor("RWK0")).toBe("SBUF-eligible");
  });

  it("SBUF branch reads level/cap verbatim, high-util at ≥24", () => {
    // Given: the live tick row at step 150
    const sbuf = sbufPanelFor(panelTickAt(150));
    // Then: level equals payload, cap 30, threshold ≥80%
    expect(sbuf.id).toBe("SBUF");
    expect(sbuf.level).toBe(F.ticks["150"]?.sbuf_level);
    expect(sbuf.cap).toBe(SBUF_CAP);
    expect(SBUF_HIGH).toBeGreaterThanOrEqual(24);
    expect(sbuf.high).toBe((F.ticks["150"]?.sbuf_level ?? 0) >= 24);
    expect(sbuf.noSeriesLabel).toBe("no per-step series");
  });

  it("_C7TAIL special shows final + no-series label", () => {
    const panel = machinePanelFor(panelTickAt(299), "_C7TAIL");
    expect(panel.found).toBe(true);
    if (!panel.found || panel.kind !== "c7tail") return;
    expect(panel.c7tailFinal).toBe(F.c7tail_final);
    expect(panel.noSeriesLabel).toBe("no per-step series");
  });
});
