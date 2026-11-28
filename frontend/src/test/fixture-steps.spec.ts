// FE-3 (PRISSUE-67 follow-up): multi-step fixture coverage.
//
// The A-777 tick fixture carries sparse but CONSECUTIVE twin rows so specs
// can assert across steps (warm-up deltas, fault onset/offset transitions)
// without hand-made physics: every row is a verbatim
// services.sim_bridge.schema build_tick dump of run_episode(777,
// F-21-drift-B2); the header is build_header; digest is replay_digest.
// Step runs: warm-up 0-2, onset 149-152, offset 161-163, tail 298-299.
import { describe, expect, it } from "vitest";
import fixture from "./fixtures/ticks-A-777.json";
import { BUFFER_CAPS } from "../components/panels/machineMeta";
import { BUFFER_IDS } from "../store/tick";

interface FixtureTick {
  readonly step: number;
  readonly states: readonly string[];
  readonly obs: readonly number[];
  readonly throughput: readonly number[];
  readonly buffers: readonly number[];
  readonly sbuf_level: number;
  readonly events_at_k: ReadonlyArray<Record<string, unknown>>;
  readonly faults: ReadonlyArray<Readonly<Record<string, unknown>>>;
  readonly quality: Readonly<Record<string, unknown>>;
  readonly currents: readonly number[];
}

interface FixtureShape {
  readonly code_version: string;
  readonly digest: string;
  readonly fault: string;
  readonly schema_version: number;
  readonly seed: number;
  readonly header: {
    readonly seed: number;
    readonly T: number;
    readonly c7tail_final: number;
    readonly sbuf_stats: Readonly<Record<string, unknown>>;
    readonly flow_stats: Readonly<Record<string, unknown>>;
    readonly energy: Readonly<Record<string, unknown>>;
  };
  readonly ticks: ReadonlyArray<FixtureTick>;
}

const F = fixture as unknown as FixtureShape;

// Runs of consecutive steps the fixture must carry (warm-up, onset, offset, tail).
const RUNS = [
  [0, 1, 2],
  [149, 150, 151, 152],
  [161, 162, 163],
  [298, 299],
] as const;
const STEPS = RUNS.flat();

function tickAt(step: number): FixtureTick {
  const t = F.ticks.find((k) => k.step === step);
  if (t === undefined) throw new Error(`fixture missing step ${step}`);
  return t;
}

function eventsAt(step: number): ReadonlyArray<Record<string, unknown>> {
  return tickAt(step).events_at_k;
}

describe("FE-3 fixture lineage (twin/bridge generated, never hand-written)", () => {
  it("pins seed 777 / T 300 / F-21-drift-B2 / schema 6 / twin-2.5.0", () => {
    expect(F.seed).toBe(777);
    expect(F.header.seed).toBe(777);
    expect(F.header.T).toBe(300);
    expect(F.fault).toBe("F-21-drift-B2");
    expect(F.schema_version).toBe(6);
    expect(F.code_version).toBe("twin-2.5.0-topology-A");
    expect(F.digest).toMatch(/^[0-9a-f]{64}$/);
    expect(F.digest).toBe(
      "3a1837ecf28c3c07a11fba62f5e91e553fca11e646104227e6e5c2ab35eee0e1",
    );
  });

  it("carries exactly the consecutive step runs (warm-up/onset/offset/tail)", () => {
    expect(F.ticks.map((t) => t.step)).toEqual([...STEPS]);
    for (const run of RUNS) {
      for (let i = 1; i < run.length; i += 1) {
        expect(run[i]).toBe((run[i - 1] ?? 0) + 1);
      }
    }
  });

  it("header finals are honest (c7tail int, energy apparent-only)", () => {
    expect(Number.isInteger(F.header.c7tail_final)).toBe(true);
    expect(F.header.energy["unit"]).toBe("kVAh-apparent");
  });
});

describe("FE-3 frozen shape on every row", () => {
  for (const step of STEPS) {
    it(`step ${step}: 26-wide rows, tput domain {0,1}, sbuf invariant`, () => {
      const t = tickAt(step);
      expect(t.states).toHaveLength(26);
      expect(t.obs).toHaveLength(26);
      expect(t.throughput).toHaveLength(26);
      expect(t.buffers).toHaveLength(26);
      expect(t.currents).toHaveLength(26);
      for (const v of t.throughput) expect([0, 1]).toContain(v);
      const sbufIdx = BUFFER_IDS.indexOf("SBUF");
      expect(t.sbuf_level).toBe(t.buffers[sbufIdx]);
      t.buffers.forEach((lvl, j) => {
        const id = BUFFER_IDS[j] ?? "";
        const cap = (BUFFER_CAPS as Readonly<Record<string, number>>)[id];
        expect(cap).toBeDefined();
        expect(lvl).toBeGreaterThanOrEqual(0);
        expect(lvl).toBeLessThanOrEqual(cap ?? 0);
      });
      for (const v of t.currents) {
        expect(Number.isFinite(v)).toBe(true);
        expect(v).toBeGreaterThanOrEqual(0);
      }
      expect("temperature" in t).toBe(false);
      expect("temp" in t).toBe(false);
    });

    it(`step ${step}: quality is parts-last join or no-part-yet`, () => {
      const t = tickAt(step);
      for (const [m, entry] of Object.entries(t.quality)) {
        if (entry === "no completed part yet") continue;
        expect(typeof entry).toBe("object");
        const e = entry as Record<string, unknown>;
        expect(e["source"]).toBe("parts-last");
        expect(["OK", "DEGRADE", "REJECT"]).toContain(e["flag"]);
        // Twin part ids are numeric (AGV delivery sequence numbers).
        expect(Number.isInteger(e["part_id"])).toBe(true);
        expect(m.length).toBeGreaterThan(0);
      }
    });
  }
});

describe("FE-3 multi-step assertions (need consecutive rows)", () => {
  it("warm-up: step 0 opens starved, step 1 quiet, step 2 drops PKG2", () => {
    const on0 = eventsAt(0).filter((e) => e["event"] === "STARVE_ON");
    expect(on0.length).toBeGreaterThan(0);
    expect(eventsAt(1)).toHaveLength(0);
    const down2 = eventsAt(2).filter((e) => e["event"] === "DOWN");
    expect(down2.map((e) => e["machine"])).toEqual(["PKG2"]);
  });

  it("onset: FAULT_START fires only at step 150 on B2 across 149-152", () => {
    for (const k of [149, 151, 152] as const) {
      expect(
        eventsAt(k).filter((e) => e["event"] === "FAULT_START"),
        `step ${k}`,
      ).toHaveLength(0);
    }
    const starts = eventsAt(150).filter((e) => e["event"] === "FAULT_START");
    expect(starts).toHaveLength(1);
    expect(starts[0]?.["machine"]).toBe("B2");
    expect(
      (starts[0]?.["detail"] as Record<string, unknown> | undefined)?.[
        "fault_id"
      ],
    ).toBe("F-21");
  });

  it("offset: FAULT_END fires only at step 162 on B2 across 161-163", () => {
    for (const k of [161, 163] as const) {
      expect(
        eventsAt(k).filter((e) => e["event"] === "FAULT_END"),
        `step ${k}`,
      ).toHaveLength(0);
    }
    const ends = eventsAt(162).filter((e) => e["event"] === "FAULT_END");
    expect(ends).toHaveLength(1);
    expect(ends[0]?.["machine"]).toBe("B2");
  });

  it("consecutive rows share roster shape (states/obs align step to step)", () => {
    for (const run of RUNS) {
      for (let i = 1; i < run.length; i += 1) {
        const a = tickAt(run[i - 1] ?? -1);
        const b = tickAt(run[i] ?? -1);
        expect(b.step).toBe(a.step + 1);
        expect(b.states).toHaveLength(a.states.length);
        expect(b.obs).toHaveLength(a.obs.length);
        expect(b.buffers).toHaveLength(a.buffers.length);
      }
    }
  });
});
