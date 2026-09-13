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
  // Line A: 10 machines (Machining Line)
  A0: { x: 80, y: 100 },
  A1: { x: 230, y: 100 },
  A2: { x: 380, y: 100 },
  A3: { x: 530, y: 100 },
  A4: { x: 680, y: 100 },
  A5: { x: 830, y: 100 },
  A6: { x: 980, y: 100 },
  A7: { x: 1130, y: 100 },
  A8: { x: 1280, y: 100 },
  A9: { x: 1430, y: 100 },

  // Line B: 10 machines (Forming & Treatment Line)
  B0: { x: 80, y: 240 },
  B1: { x: 230, y: 240 },
  B2: { x: 380, y: 240 },
  B3: { x: 530, y: 240 },
  B4: { x: 680, y: 240 },
  B5: { x: 830, y: 240 },
  B6: { x: 980, y: 240 },
  B7: { x: 1130, y: 240 },
  B8: { x: 1280, y: 240 },
  B9: { x: 1430, y: 240 },

  // Line C: 8 machines (Secondary Stamping Line)
  C0: { x: 80, y: 380 },
  C1: { x: 230, y: 380 },
  C2: { x: 380, y: 380 },
  C3: { x: 530, y: 380 },
  C4: { x: 680, y: 380 },
  C5: { x: 830, y: 380 },
  C6: { x: 980, y: 380 },
  C7: { x: 1130, y: 380 },

  // Logistics & Store Nodes
  _C7TAIL: { x: 1280, y: 380 },
  SBUF: { x: 1610, y: 140 },

  // Assembly Cell: East of lines
  ASM0: { x: 1780, y: 240 },
  ASM1: { x: 1940, y: 240 },
  ASM2: { x: 2100, y: 240 },

  // Rework Bay
  RWK0: { x: 1940, y: 380 },
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
