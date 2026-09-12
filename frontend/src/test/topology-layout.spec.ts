import { describe, expect, it } from "vitest";
import { EXPECTED_EDGE_COUNT, PINNED_EDGES } from "../topology/edges";
import { NODE_HEIGHT, NODE_WIDTH, computeLayout, hasOverlap } from "../topology/layout";
import { EXPECTED_NODE_COUNT, PINNED_NODES } from "../topology/nodes";

// Failing-first: written before final layout; red on empty scaffold.
describe("topology contract", () => {
  it("pins 34 nodes (32 machines + SBUF + _C7TAIL)", () => {
    expect(PINNED_NODES).toHaveLength(EXPECTED_NODE_COUNT);
    expect(EXPECTED_NODE_COUNT).toBe(34);
    const ids = new Set(PINNED_NODES.map((n) => n.id));
    expect(ids.has("SBUF")).toBe(true);
    expect(ids.has("_C7TAIL")).toBe(true);
  });

  it("pins 36 edges with class census 25/3/4/2/2", () => {
    expect(PINNED_EDGES).toHaveLength(EXPECTED_EDGE_COUNT);
    expect(EXPECTED_EDGE_COUNT).toBe(36);
    const census = new Map<string, number>();
    for (const e of PINNED_EDGES) {
      census.set(e.data.edgeClass, (census.get(e.data.edgeClass) ?? 0) + 1);
    }
    expect(census.get("line-gap")).toBe(25);
    expect(census.get("tail-stage")).toBe(3);
    expect(census.get("agv-drain")).toBe(4);
    expect(census.get("assembly")).toBe(2);
    expect(census.get("rework")).toBe(2);
  });

  it("dagre layout has no overlap at 2x sprite scale WITH the rework cycle", () => {
    const laid = computeLayout(PINNED_NODES, PINNED_EDGES);
    expect(laid).toHaveLength(34);
    // Cycle present: ASM2→RWK0 back-edge + RWK0→ASM0 close the loop.
    const back = PINNED_EDGES.filter((e) => e.data.backEdge);
    expect(back).toHaveLength(1);
    expect(back[0]?.source).toBe("ASM2");
    expect(hasOverlap(laid, { width: NODE_WIDTH, height: NODE_HEIGHT })).toBe(false);
  });
});
