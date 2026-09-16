import { describe, expect, it } from "vitest";
import fixture from "../test/fixtures/ticks-A-777.json";
import { BUFFER_CAPS } from "../components/panels/machineMeta";
import { bufferBarsFor, type PanelTick } from "../components/panels/selectors";
import { PINNED_EDGES, bufferIdForEdge, widthForUtil } from "../topology/edges";

// Todo 7 bridge fixture shape (schema v2): header carries the buffer census
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
    readonly quality: Readonly<Record<string, unknown>>;
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
  return {
    step: t.step,
    states: t.states,
    obs: t.obs,
    throughput: t.throughput,
    buffers: t.buffers,
    sbuf_level: t.sbuf_level,
    quality: t.quality,
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
  it("topology-A fixture carries 26 machines x 26 buffers", () => {
    expect(MACHINE_ORDER).toHaveLength(26);
    expect(BUFFER_ORDER).toHaveLength(26);
    for (const t of F.ticks) {
      expect(t.states).toHaveLength(26);
      expect(t.buffers).toHaveLength(26);
    }
  });

  it("all 31 widths stay in [1,4] at a live step", () => {
    const widths = widthsAt(150);
    expect(widths.size).toBe(31);
    for (const w of widths.values()) {
      expect(w).toBeGreaterThanOrEqual(1);
      expect(w).toBeLessThanOrEqual(4);
    }
  });

  it("higher util renders a wider stroke (monotonic over mapped edges)", () => {
    const tick = panelTickAt(150);
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
    const widths = widthsAt(150);
    expect(widths.get(hi.id) ?? 0).toBeGreaterThan(widths.get(lo.id) ?? 0);
  });

  it("SBUF drain width equals widthForUtil of the live SBUF util", () => {
    const tick = panelTickAt(150);
    const sbuf = bufferBarsFor(tick).find((b) => b.id === "SBUF");
    if (sbuf === undefined) throw new Error("SBUF bar missing");
    expect(widthsAt(150).get("e-SBUF-kit")).toBeCloseTo(widthForUtil(sbuf.util), 9);
  });

  it("storeless edges stay flat at 1 while mapped edges move across steps", () => {
    const a = widthsAt(0);
    const b = widthsAt(299);
    for (const id of ["e-C7-tail", "e-RWK0-ASM0", "e-tail-kit"]) {
      expect(a.get(id)).toBe(1);
      expect(b.get(id)).toBe(1);
    }
    const moved = PINNED_EDGES.some(
      (e) => bufferIdForEdge(e) !== null && a.get(e.id) !== b.get(e.id),
    );
    expect(moved).toBe(true);
  });
});
