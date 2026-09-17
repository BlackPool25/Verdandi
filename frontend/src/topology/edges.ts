import { BUFFER_CAPS } from "../components/panels/machineMeta";
import type { TopoEdgeDatum } from "./types";

// Pinned 31-edge inventory (topology-A). Each entry maps to its twin class:
//   line-gap (16): A0-A1,A1-A2,A2-A7,A7-A8,A8-A9 (5) + B0-B1,B1-B2,B2-B7P,
//     B2-B7S,B7P-B8,B7S-B8,B8-B9 (7) + C0-C1,C1-C2,C2-C6,C6-C7 (4) —
//     twin _line_edges (A27/C26 gap buffers, B2 fork, B7P/B7S join).
//   tail-stage (4): A9→GA9, B9→GB9, C7→_C7TAIL, C7→PKG0/C7PKG —
//     twin _TAIL_BUF + C7PKG fork feed. GA9/GB9 are buffers, not nodes,
//     so A9→SBUF / B9→SBUF carry the GA9/GB9 label.
//   agv-drain (4): GA9→kit, GB9→kit, _C7TAIL→kit, SBUF→kit — twin _agv drain
//     to kit intake (kit intake == ASM0, the single node that can receive).
//     GA9/GB9 drains render as A9→ASM0 / B9→ASM0 AGV edges (buffer→kit hop
//     with the tail machine as the visible source).
//   assembly (3): ASM01, INSP01, INSP02 — twin _asm0_process / _asm_mid_process
//     (ASM1→INSP0→ASM2; ASM12 retired).
//   rework (2): ASM2→RWK_RET, RWK0→kitC — twin ASM2→RWK0→ASM0-kit loop.
//     ASM2→RWK0 is the dagre back-edge closing the cycle (see layout.ts).
//   packaging (2): PKG01, PKG02 — twin PKG0 round-robin fork to PKG1/PKG2.
export interface PinnedEdge {
  readonly id: string;
  readonly source: string;
  readonly target: string;
  readonly data: TopoEdgeDatum;
}

function lineGapEdges(): readonly PinnedEdge[] {
  const chains: ReadonlyArray<readonly string[]> = [
    ["A0", "A1", "A2", "A7", "A8", "A9"],
    ["B0", "B1", "B2"],
    ["B8", "B9"],
    ["C0", "C1", "C2", "C6", "C7"],
  ];
  const out: PinnedEdge[] = [];
  for (const chain of chains) {
    for (let i = 0; i < chain.length - 1; i += 1) {
      const source = chain[i] as string;
      const target = chain[i + 1] as string;
      out.push({
        id: `e-${source}-${target}`,
        source,
        target,
        data: { label: `${source}${target.slice(1)}`, edgeClass: "line-gap" },
      });
    }
  }
  out.push(
    { id: "e-B2-B7P", source: "B2", target: "B7P", data: { label: "B2B7P", edgeClass: "line-gap" } },
    { id: "e-B2-B7S", source: "B2", target: "B7S", data: { label: "B2B7S", edgeClass: "line-gap" } },
    { id: "e-B7P-B8", source: "B7P", target: "B8", data: { label: "B7PB8", edgeClass: "line-gap" } },
    { id: "e-B7S-B8", source: "B7S", target: "B8", data: { label: "B7SB8", edgeClass: "line-gap" } },
  );
  return out;
}

const REST: readonly PinnedEdge[] = [
  // tail-stage (4)
  { id: "e-A9-SBUF", source: "A9", target: "SBUF", data: { label: "GA9", edgeClass: "tail-stage" } },
  { id: "e-B9-SBUF", source: "B9", target: "SBUF", data: { label: "GB9", edgeClass: "tail-stage" } },
  { id: "e-C7-tail", source: "C7", target: "_C7TAIL", data: { label: "_C7TAIL", edgeClass: "tail-stage" } },
  { id: "e-C7-PKG0", source: "C7", target: "PKG0", data: { label: "C7PKG", edgeClass: "tail-stage" } },
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
  // assembly (3)
  { id: "e-ASM0-ASM1", source: "ASM0", target: "ASM1", data: { label: "ASM01", edgeClass: "assembly" } },
  { id: "e-ASM1-INSP0", source: "ASM1", target: "INSP0", data: { label: "INSP01", edgeClass: "assembly" } },
  { id: "e-INSP0-ASM2", source: "INSP0", target: "ASM2", data: { label: "INSP02", edgeClass: "assembly" } },
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
  // packaging (2)
  { id: "e-PKG0-PKG1", source: "PKG0", target: "PKG1", data: { label: "PKG01", edgeClass: "packaging" } },
  { id: "e-PKG0-PKG2", source: "PKG0", target: "PKG2", data: { label: "PKG02", edgeClass: "packaging" } },
] as const;

export const PINNED_EDGES: readonly PinnedEdge[] = [...lineGapEdges(), ...REST];

export const EXPECTED_EDGE_COUNT = 31;

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
