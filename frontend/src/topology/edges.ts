import { BUFFER_CAPS } from "../components/panels/machineMeta";
import type { TopoEdgeDatum } from "./types";

// Pinned 36-edge inventory. Each entry maps to its twin class:
//   line-gap (25): A01..A89 (9) + B01..B89 (9) + C01..C67 (7) — twin _line_edges.
//   tail-stage (3): A9→GA9, B9→GB9, C7→_C7TAIL — twin _TAIL_BUF. GA9/GB9 are
//     buffers, not nodes, so A9→SBUF / B9→SBUF carry the GA9/GB9 label.
//   agv-drain (4): GA9→kit, GB9→kit, _C7TAIL→kit, SBUF→kit — twin _agv drain
//     to kit intake (kit intake == ASM0, the single node that can receive).
//     GA9/GB9 drains render as A9→ASM0 / B9→ASM0 AGV edges (buffer→kit hop
//     with the tail machine as the visible source).
//   assembly (2): ASM01, ASM12 — twin _asm0_process / _asm_mid_process.
//   rework (2): ASM2→RWK_RET, RWK0→kitC — twin ASM2→RWK0→ASM0-kit loop.
//     ASM2→RWK0 is the dagre back-edge closing the cycle (see layout.ts).
export interface PinnedEdge {
  readonly id: string;
  readonly source: string;
  readonly target: string;
  readonly data: TopoEdgeDatum;
}

function lineGapEdges(): readonly PinnedEdge[] {
  const out: PinnedEdge[] = [];
  for (let i = 0; i < 9; i += 1) {
    out.push({
      id: `e-A${i}-A${i + 1}`,
      source: `A${i}`,
      target: `A${i + 1}`,
      data: { label: `A${i}${i + 1}`, edgeClass: "line-gap" },
    });
  }
  for (let i = 0; i < 9; i += 1) {
    out.push({
      id: `e-B${i}-B${i + 1}`,
      source: `B${i}`,
      target: `B${i + 1}`,
      data: { label: `B${i}${i + 1}`, edgeClass: "line-gap" },
    });
  }
  for (let i = 0; i < 7; i += 1) {
    out.push({
      id: `e-C${i}-C${i + 1}`,
      source: `C${i}`,
      target: `C${i + 1}`,
      data: { label: `C${i}${i + 1}`, edgeClass: "line-gap" },
    });
  }
  return out;
}

const REST: readonly PinnedEdge[] = [
  // tail-stage (3)
  { id: "e-A9-SBUF", source: "A9", target: "SBUF", data: { label: "GA9", edgeClass: "tail-stage" } },
  { id: "e-B9-SBUF", source: "B9", target: "SBUF", data: { label: "GB9", edgeClass: "tail-stage" } },
  { id: "e-C7-tail", source: "C7", target: "_C7TAIL", data: { label: "_C7TAIL", edgeClass: "tail-stage" } },
  // agv-drain (4)
  { id: "e-A9-kit", source: "A9", target: "ASM0", data: { label: "AGV:GA9→kit", edgeClass: "agv-drain" } },
  { id: "e-B9-kit", source: "B9", target: "ASM0", data: { label: "AGV:GB9→kit", edgeClass: "agv-drain" } },
  {
    id: "e-tail-kit",
    source: "_C7TAIL",
    target: "ASM0",
    data: { label: "AGV:_C7TAIL→kit", edgeClass: "agv-drain" },
  },
  {
    id: "e-SBUF-kit",
    source: "SBUF",
    target: "ASM0",
    data: { label: "AGV:SBUF→kit", edgeClass: "agv-drain" },
  },
  // assembly (2)
  { id: "e-ASM0-ASM1", source: "ASM0", target: "ASM1", data: { label: "ASM01", edgeClass: "assembly" } },
  { id: "e-ASM1-ASM2", source: "ASM1", target: "ASM2", data: { label: "ASM12", edgeClass: "assembly" } },
  // rework (2) — ASM2→RWK0 is the cycle back-edge
  {
    id: "e-ASM2-RWK0",
    source: "ASM2",
    target: "RWK0",
    data: { label: "RWK_RET", edgeClass: "rework", backEdge: true },
  },
  {
    id: "e-RWK0-ASM0",
    source: "RWK0",
    target: "ASM0",
    data: { label: "kitC", edgeClass: "rework" },
  },
] as const;

export const PINNED_EDGES: readonly PinnedEdge[] = [...lineGapEdges(), ...REST];

export const EXPECTED_EDGE_COUNT = 36;

const AGV_BUFFER_IDS: readonly string[] = ["GA9", "GB9", "SBUF"];

export function bufferIdForEdge(edge: PinnedEdge): string | null {
  const label = edge.data.label;
  if (label in BUFFER_CAPS) return label;
  for (const id of AGV_BUFFER_IDS) {
    if (label.includes(id)) return id;
  }
  return null;
}

export function widthForUtil(util: number): number {
  const u = Number.isFinite(util) ? Math.min(1, Math.max(0, util)) : 0;
  return 1 + u * 3;
}
