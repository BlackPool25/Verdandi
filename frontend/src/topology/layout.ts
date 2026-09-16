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
  // Line A: 6 machines (Machining Line; A3-A6 cut, A2->A7 gap)
  A0: { x: 80, y: 100 },
  A1: { x: 230, y: 100 },
  A2: { x: 380, y: 100 },
  A7: { x: 530, y: 100 },
  A8: { x: 680, y: 100 },
  A9: { x: 830, y: 100 },

  // Line B: 7 machines (Forming & Treatment Line; B3-B6 cut, B7 -> B7P/B7S pair)
  B0: { x: 80, y: 240 },
  B1: { x: 230, y: 240 },
  B2: { x: 380, y: 240 },
  B7P: { x: 530, y: 240 },
  B7S: { x: 530, y: 330 },
  B8: { x: 680, y: 240 },
  B9: { x: 830, y: 240 },

  // Line C: 5 machines (Secondary Stamping Line; C3-C5 cut, C2->C6 gap)
  C0: { x: 80, y: 420 },
  C1: { x: 230, y: 420 },
  C2: { x: 380, y: 420 },
  C6: { x: 530, y: 420 },
  C7: { x: 680, y: 420 },

  // Logistics & Store Nodes
  _C7TAIL: { x: 830, y: 420 },
  SBUF: { x: 1610, y: 140 },

  // Packaging fork (C7PKG feed -> PKG0 -> PKG1/PKG2 sinks)
  PKG0: { x: 980, y: 420 },
  PKG1: { x: 1130, y: 420 },
  PKG2: { x: 1055, y: 540 },

  // Assembly Cell: East of lines (ASM1->INSP0->ASM2; ASM12 retired)
  ASM0: { x: 1780, y: 240 },
  ASM1: { x: 1940, y: 240 },
  INSP0: { x: 2100, y: 240 },
  ASM2: { x: 2260, y: 240 },

  // Rework Bay
  RWK0: { x: 2100, y: 380 },
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
