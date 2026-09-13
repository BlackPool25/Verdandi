// Task 1 TDD: honest aggregate selectors over the frozen tick payload.
import { describe, expect, it } from "vitest";
import fixture from "../../test/fixtures/ticks-777.json";
import { SBUF_HIGH } from "./machineMeta";
import {
  episodeStatsFor,
  lineStatsFor,
  type EpisodeHeader,
  type PanelTick,
} from "./selectors";
import { toPatch, type LiveTick } from "../../sim/streamCodec";
import { STREAM_MACHINE_ORDER } from "../../sim/streamCodec";

interface FixtureTick {
  readonly step: number;
  readonly states: readonly string[];
  readonly obs: readonly number[];
  readonly throughput: readonly number[];
  readonly buffers: readonly number[];
  readonly sbuf_level: number;
  readonly quality: Readonly<Record<string, unknown>>;
}

interface FixtureShape {
  readonly machine_order: readonly string[];
  readonly buffer_order: readonly string[];
  readonly ticks: Readonly<Record<string, FixtureTick>>;
  readonly c7tail_final: number;
}

const F = fixture as unknown as FixtureShape;
const PROBED = [0, 119, 150, 162, 299] as const;

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

describe("lineStatsFor: honest per-tick aggregates", () => {
  for (const step of PROBED) {
    it(`step ${step}: tput sum bounded, state counts sum 32, mean/sbuf honest`, () => {
      // Given: the live tick row at this step
      const tick = panelTickAt(step);
      const raw = F.ticks[String(step)] as FixtureTick;
      // When: aggregating the line
      const s = lineStatsFor(tick);
      // Then: throughput sum equals payload sum within 0..32
      const expectedTput = raw.throughput.reduce((a, b) => a + b, 0);
      expect(s.tputSum).toBe(expectedTput);
      expect(s.tputSum).toBeGreaterThanOrEqual(0);
      expect(s.tputSum).toBeLessThanOrEqual(32);
      // Then: state counts partition the 32-machine roster
      expect(s.run + s.blocked + s.starved + s.down).toBe(32);
      expect(s.run).toBe(raw.states.filter((x) => x === "RUN").length);
      expect(s.blocked).toBe(raw.states.filter((x) => x === "BLOCKED").length);
      expect(s.starved).toBe(raw.states.filter((x) => x === "STARVED").length);
      expect(s.down).toBe(raw.states.filter((x) => x === "DOWN").length);
      // Then: mean obs + sbuf level pass the payload through
      const expectedMean = raw.obs.reduce((a, b) => a + b, 0) / raw.obs.length;
      expect(s.meanObs).toBeCloseTo(expectedMean, 9);
      expect(s.sbufLevel).toBe(raw.sbuf_level);
      expect(s.sbufHigh).toBe(raw.sbuf_level >= 24);
    });
  }

  it("SBUF high-util threshold is >= 24 (80% of cap 30)", () => {
    expect(SBUF_HIGH).toBeGreaterThanOrEqual(24);
  });

  it("synthetic all-RUN tick: run=32, rest 0", () => {
    const tick = panelTickAt(0);
    const all: PanelTick = {
      ...tick,
      states: Array.from({ length: 32 }, () => "RUN"),
      throughput: Array.from({ length: 32 }, () => 1),
    };
    const s = lineStatsFor(all);
    expect(s.run).toBe(32);
    expect(s.blocked + s.starved + s.down).toBe(0);
    expect(s.tputSum).toBe(32);
  });
});

describe("episodeStatsFor: honest finals, missing -> null", () => {
  const full: EpisodeHeader = {
    sbuf_stats: { diverted: 7, drained: 5, max_occupancy: 26 },
    flow_stats: { sunk: 41, scrapped: 3, rejected: 2, reworked: 4, c7tail: 0 },
    c7tail_final: 0,
  };

  it("full header passes finals through", () => {
    const s = episodeStatsFor(full);
    expect(s.diverted).toBe(7);
    expect(s.drained).toBe(5);
    expect(s.sbufMax).toBe(26);
    expect(s.sunk).toBe(41);
    expect(s.scrapped).toBe(3);
    expect(s.rejected).toBe(2);
    expect(s.reworked).toBe(4);
    expect(s.c7tailFinal).toBe(0);
  });

  it("null header -> all null (no fabricated zeros)", () => {
    const s = episodeStatsFor(null);
    expect(s.diverted).toBeNull();
    expect(s.drained).toBeNull();
    expect(s.sbufMax).toBeNull();
    expect(s.sunk).toBeNull();
    expect(s.scrapped).toBeNull();
    expect(s.rejected).toBeNull();
    expect(s.reworked).toBeNull();
    expect(s.c7tailFinal).toBeNull();
  });

  it("missing keys -> null for those keys only", () => {
    const s = episodeStatsFor({ flow_stats: { sunk: 9 } });
    expect(s.sunk).toBe(9);
    expect(s.diverted).toBeNull();
    expect(s.drained).toBeNull();
    expect(s.sbufMax).toBeNull();
    expect(s.scrapped).toBeNull();
    expect(s.rejected).toBeNull();
    expect(s.reworked).toBeNull();
    expect(s.c7tailFinal).toBeNull();
  });

  it("c7tail falls back to flow_stats.c7tail when top-level final missing", () => {
    const s = episodeStatsFor({ flow_stats: { c7tail: 2 } });
    expect(s.c7tailFinal).toBe(2);
  });
});

describe("TickPatch optional buffers (edge width)", () => {
  it("toPatch without buffers still satisfies TickPatch", () => {
    const row: LiveTick = {
      step: 1,
      states: Array.from({ length: STREAM_MACHINE_ORDER.length }, () => "RUN"),
      throughput: Array.from({ length: STREAM_MACHINE_ORDER.length }, () => 0),
    };
    const patch = toPatch(row);
    expect(patch.step).toBe(1);
    expect(patch.buffers).toBeUndefined();
    // Buffers attach optionally for edge width without breaking the patch.
    const withBuffers = { ...patch, buffers: { A01: 3 } };
    expect(withBuffers.buffers?.["A01"]).toBe(3);
  });
});
