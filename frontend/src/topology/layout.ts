import dagre from "dagre";
import type { PinnedEdge } from "./edges";
import type { PinnedNode } from "./nodes";

export interface LaidOutNode {
  readonly id: string;
  readonly x: number;
  readonly y: number;
}

// Flow direction: FLOOR (structured industrial factory floor plan), LR (dagre default), TB (vertical).
export type RankDir = "FLOOR" | "LR" | "TB";

// Sprite footprint at 2x scale (T6 sprites are rect-grid; 2x keeps text crisp).
export const NODE_WIDTH = 120;
export const NODE_HEIGHT = 60;

export interface LayoutSize {
  readonly width: number;
  readonly height: number;
}

const FLOOR_POSITIONS: Readonly<Record<string, { readonly x: number; readonly y: number }>> = {
  // Line A: 6 machines (Machining Line; Row 1: y = 50)
  A0: { x: 50, y: 50 },
  A1: { x: 190, y: 50 },
  A2: { x: 330, y: 50 },
  A7: { x: 470, y: 50 },
  A8: { x: 610, y: 50 },
  A9: { x: 750, y: 50 },

  // Line B: 7 machines (Forming & Treatment Line; Row 2: y = 180; B7P at y = 145, B7S at y = 225)
  B0: { x: 50, y: 180 },
  B1: { x: 190, y: 180 },
  B2: { x: 330, y: 180 },
  B7P: { x: 470, y: 145 },
  B7S: { x: 470, y: 225 },
  B8: { x: 610, y: 180 },
  B9: { x: 750, y: 180 },

  // Line C: 5 machines (Secondary Stamping Line; Row 3: y = 330)
  C0: { x: 50, y: 330 },
  C1: { x: 190, y: 330 },
  C2: { x: 330, y: 330 },
  C6: { x: 470, y: 330 },
  C7: { x: 610, y: 330 },

  // Logistics & Store Nodes
  _C7TAIL: { x: 750, y: 330 },
  SBUF: { x: 890, y: 105 },

  // Packaging Fork & Sinks (direct feed from C7 at x=610)
  PKG0: { x: 610, y: 440 },
  PKG1: { x: 750, y: 415 },
  PKG2: { x: 750, y: 495 },

  // Final Assembly & Test Cell (East of feeder lines: parts converge cleanly into ASM0!)
  ASM0: { x: 1000, y: 200 },
  ASM1: { x: 1140, y: 200 },
  INSP0: { x: 1280, y: 200 },
  ASM2: { x: 1420, y: 200 },

  // Rework Bay (under INSP0, clean repair loop)
  RWK0: { x: 1280, y: 310 },
};

// Precompute layout on topology change ONLY (never per tick).
export function computeLayout(
  nodes: readonly PinnedNode[],
  edges: readonly PinnedEdge[],
  size: LayoutSize = { width: NODE_WIDTH, height: NODE_HEIGHT },
  rankdir: RankDir = "LR",
): readonly LaidOutNode[] {
  if (rankdir === "FLOOR") {
    return nodes.map((n) => {
      const p = FLOOR_POSITIONS[n.id] ?? { x: 0, y: 0 };
      return { id: n.id, x: p.x, y: p.y };
    });
  }
  const g = new dagre.graphlib.Graph();
  g.setGraph({ rankdir, nodesep: 60, ranksep: 80 });
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
