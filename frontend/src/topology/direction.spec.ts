import { describe, expect, it } from "vitest";
import { PINNED_EDGES } from "./edges";
import { NODE_HEIGHT, NODE_WIDTH, computeLayout, hasOverlap } from "./layout";
import { PINNED_NODES } from "./nodes";

describe("direction toggle re-layout", () => {
  it("default rankdir stays LR (back-compat with the pinned snapshot)", () => {
    const implicit = computeLayout(PINNED_NODES, PINNED_EDGES);
    const explicit = computeLayout(PINNED_NODES, PINNED_EDGES, undefined, "LR");
    expect(implicit).toEqual(explicit);
  });

  it("TB layout is lossless: same 34 ids, no overlap, positions actually change", () => {
    const lr = computeLayout(PINNED_NODES, PINNED_EDGES, undefined, "LR");
    const tb = computeLayout(PINNED_NODES, PINNED_EDGES, undefined, "TB");
    expect(tb).toHaveLength(34);
    expect(new Set(tb.map((n) => n.id))).toEqual(new Set(lr.map((n) => n.id)));
    expect(hasOverlap(tb, { width: NODE_WIDTH, height: NODE_HEIGHT })).toBe(false);
    expect(tb).not.toEqual(lr);
  });
});
