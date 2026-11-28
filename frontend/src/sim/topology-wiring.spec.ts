import { describe, expect, it } from "vitest";
import fixture from "../test/fixtures/ticks-A-777.json";
import { BUFFER_CAPS } from "../components/panels/machineMeta";
import { toFaultSpec } from "../components/events/anomaly";
import type { FaultSpec } from "../components/events/types";
import { parseFeedEvents } from "./streamCodec";
import { bufferBarsFor, type PanelTick } from "../components/panels/selectors";
import { PINNED_EDGES, bufferIdForEdge, widthForUtil } from "../topology/edges";
import {
  EDGE_COUNT,
  FINAL_STEP,
  FIRST_STEP,
  LIVE_STEP,
  MACHINE_COUNT,
  SBUF_ID,
  SBUF_KIT_EDGE_ID,
  STORELESS_EDGE_IDS,
} from "../test/testConstants";

// Todo 7 bridge fixture shape (schema v6, twin-2.5.0-topology-A): header carries the buffer census
// via flow_stats.store_final (26 buffers + _C7TAIL store); ticks is a sparse
// step list with 26-wide states/obs/throughput/buffers rows.
interface FixtureShape {
  readonly header: {
    readonly flow_stats: { readonly store_final: Readonly<Record<string, number>> };
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

// Buffer order: the twin BUFFERS order carried by store_final, minus the
// _C7TAIL store (a store, not a buffer row). Tick buffers rows align 1:1.
const BUFFER_ORDER: readonly string[] = Object.keys(F.header.flow_stats.store_final).filter(
  (id) => id in BUFFER_CAPS,
);
const MACHINE_ORDER: readonly string[] = Object.keys(F.ticks[0]?.quality ?? {});

function panelTickAt(step: number): PanelTick {
  const t = F.ticks.find((k) => k.step === step);
  if (t === undefined) throw new Error(`fixture missing step ${step}`);
  const faults: FaultSpec[] = [];
  for (const f of t.faults ?? []) {
    if (typeof f !== "object" || f === null || Array.isArray(f)) continue;
    try {
      faults.push(toFaultSpec(f as Record<string, unknown>));
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

function widthsAt(step: number): Map<string, number> {
  const tick = panelTickAt(step);
  const util = new Map(bufferBarsFor(tick).map((b) => [b.id, b.util] as const));
  const out = new Map<string, number>();
  for (const e of PINNED_EDGES) {
    const buf = bufferIdForEdge(e);
    out.set(e.id, buf === null ? 1 : widthForUtil(util.get(buf) ?? 0));
  }
  return out;
}

describe("sim wiring: edge widths track live buffer util", () => {
  it(`topology-A fixture carries ${MACHINE_COUNT} machines x ${MACHINE_COUNT} buffers`, () => {
    expect(MACHINE_ORDER).toHaveLength(MACHINE_COUNT);
    expect(BUFFER_ORDER).toHaveLength(MACHINE_COUNT);
    for (const t of F.ticks) {
      expect(t.states).toHaveLength(MACHINE_COUNT);
      expect(t.buffers).toHaveLength(MACHINE_COUNT);
    }
  });

  it(`all ${EDGE_COUNT} widths stay in [1,4] at a live step`, () => {
    const widths = widthsAt(LIVE_STEP);
    expect(widths.size).toBe(EDGE_COUNT);
    for (const w of widths.values()) {
      expect(w).toBeGreaterThanOrEqual(1);
      expect(w).toBeLessThanOrEqual(4);
    }
  });

  it("higher util renders a wider stroke (monotonic over mapped edges)", () => {
    const tick = panelTickAt(LIVE_STEP);
    const util = new Map(bufferBarsFor(tick).map((b) => [b.id, b.util] as const));
    const mapped = PINNED_EDGES.filter((e) => bufferIdForEdge(e) !== null);
    let lo = { u: Number.POSITIVE_INFINITY, id: "" };
    let hi = { u: Number.NEGATIVE_INFINITY, id: "" };
    for (const e of mapped) {
      const u = util.get(bufferIdForEdge(e) ?? "") ?? 0;
      if (u < lo.u) lo = { u, id: e.id };
      if (u > hi.u) hi = { u, id: e.id };
    }
    expect(hi.u).toBeGreaterThan(lo.u);
    const widths = widthsAt(LIVE_STEP);
    expect(widths.get(hi.id) ?? 0).toBeGreaterThan(widths.get(lo.id) ?? 0);
  });

  it("SBUF drain width equals widthForUtil of the live SBUF util", () => {
    const tick = panelTickAt(LIVE_STEP);
    const sbuf = bufferBarsFor(tick).find((b) => b.id === SBUF_ID);
    if (sbuf === undefined) throw new Error("SBUF bar missing");
    expect(widthsAt(LIVE_STEP).get(SBUF_KIT_EDGE_ID)).toBeCloseTo(widthForUtil(sbuf.util), 9);
  });

  it("storeless edges stay flat at 1 while mapped edges move across steps", () => {
    const a = widthsAt(FIRST_STEP);
    const b = widthsAt(FINAL_STEP);
    for (const id of STORELESS_EDGE_IDS) {
      expect(a.get(id)).toBe(1);
      expect(b.get(id)).toBe(1);
    }
    const moved = PINNED_EDGES.some(
      (e) => bufferIdForEdge(e) !== null && a.get(e.id) !== b.get(e.id),
    );
    expect(moved).toBe(true);
  });
});
