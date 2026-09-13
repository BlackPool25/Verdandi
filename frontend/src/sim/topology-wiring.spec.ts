import { describe, expect, it } from "vitest";
import fixture from "../test/fixtures/ticks-777.json";
import { bufferBarsFor, type PanelTick } from "../components/panels/selectors";
import { PINNED_EDGES, bufferIdForEdge, widthForUtil } from "../topology/edges";

interface FixtureShape {
  readonly machine_order: readonly string[];
  readonly buffer_order: readonly string[];
  readonly ticks: Readonly<
    Record<
      string,
      {
        readonly step: number;
        readonly states: readonly string[];
        readonly obs: readonly number[];
        readonly throughput: readonly number[];
        readonly buffers: readonly number[];
        readonly sbuf_level: number;
        readonly quality: Readonly<Record<string, unknown>>;
      }
    >
  >;
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
  it("all 36 widths stay in [1,4] at a live step", () => {
    const widths = widthsAt(150);
    expect(widths.size).toBe(36);
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
    const tick = panelTickAt(162);
    const sbuf = bufferBarsFor(tick).find((b) => b.id === "SBUF");
    if (sbuf === undefined) throw new Error("SBUF bar missing");
    expect(widthsAt(162).get("e-SBUF-kit")).toBeCloseTo(widthForUtil(sbuf.util), 9);
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
