import dagre from "dagre";
import type { PinnedEdge } from "./edges";
import type { PinnedNode } from "./nodes";

export interface LaidOutNode {
  readonly id: string;
  readonly x: number;
  readonly y: number;
}

// Sprite footprint at 2x scale (T6 sprites are rect-grid; 2x keeps text crisp).
export const NODE_WIDTH = 120;
export const NODE_HEIGHT = 60;

export interface LayoutSize {
  readonly width: number;
  readonly height: number;
}

// Precompute dagre layout on topology change ONLY (never per tick).
// The rework edge ASM2→RWK0 closes the ASM0→ASM1→ASM2→RWK0→ASM0 cycle;
// dagre breaks cycles deterministically (greedy feedback-arc set), so the
// snapshot test asserts no-overlap WITH the cycle present.
export function computeLayout(
  nodes: readonly PinnedNode[],
  edges: readonly PinnedEdge[],
  size: LayoutSize = { width: NODE_WIDTH, height: NODE_HEIGHT },
): readonly LaidOutNode[] {
  const g = new dagre.graphlib.Graph();
  g.setGraph({ rankdir: "LR", nodesep: 60, ranksep: 80 });
  g.setDefaultEdgeLabel(() => ({}));
  for (const n of nodes) {
    g.setNode(n.id, { width: size.width, height: size.height });
  }
  for (const e of edges) {
    g.setEdge(e.source, e.target);
  }
  dagre.layout(g);
  return nodes.map((n) => {
    const p = g.node(n.id) as { readonly x: number; readonly y: number };
    return { id: n.id, x: p.x - size.width / 2, y: p.y - size.height / 2 };
  });
}

// No-overlap predicate used by the snapshot test at 2x sprite scale.
export function hasOverlap(
  laid: readonly LaidOutNode[],
  size: LayoutSize = { width: NODE_WIDTH, height: NODE_HEIGHT },
): boolean {
  for (let i = 0; i < laid.length; i += 1) {
    const a = laid[i];
    if (a === undefined) continue;
    for (let j = i + 1; j < laid.length; j += 1) {
      const b = laid[j];
      if (b === undefined) continue;
      const separated =
        a.x + size.width <= b.x ||
        b.x + size.width <= a.x ||
        a.y + size.height <= b.y ||
        b.y + size.height <= a.y;
      if (!separated) return true;
    }
  }
  return false;
}
