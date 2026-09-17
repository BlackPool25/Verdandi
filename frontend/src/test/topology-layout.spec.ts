import { describe, expect, it } from "vitest";
import { EXPECTED_EDGE_COUNT, PINNED_EDGES } from "../topology/edges";
import { NODE_HEIGHT, NODE_WIDTH, computeLayout, hasOverlap } from "../topology/layout";
import { EXPECTED_NODE_COUNT, PINNED_NODES, assertTopologyCounts } from "../topology/nodes";
import oldFixture from "./fixtures/ticks-777.json";

// Topology-A: 28 nodes (26 machines in MACHINE_INDEX order + SBUF + _C7TAIL),
// 31 edges (line-gap 16 + tail-stage 4 + agv-drain 4 + assembly 3 + rework 2 + packaging 2).
describe("topology contract", () => {
  it("pins 28 nodes (26 machines + SBUF + _C7TAIL)", () => {
    expect(PINNED_NODES).toHaveLength(EXPECTED_NODE_COUNT);
    expect(EXPECTED_NODE_COUNT).toBe(28);
    const ids = new Set(PINNED_NODES.map((n) => n.id));
    expect(ids.has("SBUF")).toBe(true);
    expect(ids.has("_C7TAIL")).toBe(true);
    for (const dropped of ["A3", "A4", "A5", "A6", "B3", "B4", "B5", "B6", "B7", "C3", "C4", "C5"]) {
      expect(ids.has(dropped)).toBe(false);
    }
    for (const added of ["B7P", "B7S", "PKG0", "PKG1", "PKG2", "INSP0"]) {
      expect(ids.has(added)).toBe(true);
    }
  });

  it("pins 31 edges with class census 16/4/4/3/2/2", () => {
    expect(PINNED_EDGES).toHaveLength(EXPECTED_EDGE_COUNT);
    expect(EXPECTED_EDGE_COUNT).toBe(31);
    const census = new Map<string, number>();
    for (const e of PINNED_EDGES) {
      census.set(e.data.edgeClass, (census.get(e.data.edgeClass) ?? 0) + 1);
    }
    expect(census.get("line-gap")).toBe(16);
    expect(census.get("tail-stage")).toBe(4);
    expect(census.get("agv-drain")).toBe(4);
    expect(census.get("assembly")).toBe(3);
    expect(census.get("rework")).toBe(2);
    expect(census.get("packaging")).toBe(2);
  });

  it("dagre layout has no overlap at 2x sprite scale WITH the rework cycle", () => {
    const laid = computeLayout(PINNED_NODES, PINNED_EDGES);
    expect(laid).toHaveLength(28);
    // Cycle present: ASM2→RWK0 back-edge + RWK0→ASM0 close the loop.
    const back = PINNED_EDGES.filter((e) => e.data.backEdge);
    expect(back).toHaveLength(1);
    expect(back[0]?.source).toBe("ASM2");
    expect(hasOverlap(laid, { width: NODE_WIDTH, height: NODE_HEIGHT })).toBe(false);
  });

  it("FLOOR layout pins every node at an explicit nonzero position", () => {
    const laid = computeLayout(PINNED_NODES, PINNED_EDGES, undefined, "FLOOR");
    expect(laid).toHaveLength(28);
    for (const n of laid) {
      expect(n.x === 0 && n.y === 0, `${n.id} falls back to (0,0)`).toBe(false);
    }
  });

  it("old 34-node fixture fails the count gate with the exact mismatch error", () => {
    const f = oldFixture as unknown as { readonly machine_order: readonly string[] };
    const oldNodes = f.machine_order.length + 2; // +SBUF +_C7TAIL
    expect(oldNodes).toBe(34);
    expect(() => assertTopologyCounts(oldNodes, 36)).toThrow(
      "topology count mismatch: expected 28/31",
    );
  });
});
