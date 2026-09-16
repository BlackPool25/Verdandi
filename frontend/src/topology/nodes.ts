import { MACHINE_META } from "../components/panels/machineMeta";
import { EXPECTED_EDGE_COUNT } from "./edges";
import { spriteFor, type MachineNodeDatum, type SpriteClass } from "./types";

// 28 nodes: 26 topology-A machines in MACHINE_INDEX order
// (A0,A1,A2,A7,A8,A9 / B0,B1,B2,B7P,B7S,B8,B9 / C0,C1,C2,C6,C7 /
// PKG0,PKG1,PKG2 / ASM0,ASM1,INSP0,ASM2,RWK0) + SBUF + _C7TAIL.
// Roster mirrors src/config.py MACHINE_INDEX; SBUF/_C7TAIL mirror the twin's
// AGV-drained stores (twin _TAIL_BUF + SBUF shed).
const MACHINES: readonly string[] = [
  "A0", "A1", "A2", "A7", "A8", "A9",
  "B0", "B1", "B2", "B7P", "B7S", "B8", "B9",
  "C0", "C1", "C2", "C6", "C7",
  "PKG0", "PKG1", "PKG2",
  "ASM0", "ASM1", "INSP0", "ASM2", "RWK0",
] as const;

export interface PinnedNode {
  readonly id: string;
  readonly data: MachineNodeDatum;
}

export const PINNED_NODES: readonly PinnedNode[] = [
  ...MACHINES.map((id) => ({ id, data: datumFor(id) })),
  { id: "SBUF", data: { label: "SBUF", kind: "sbuf" as const } },
  { id: "_C7TAIL", data: { label: "_C7TAIL", kind: "c7tail" as const } },
];

// T2: each machine id carries its MACHINE_META cls verbatim + the
// spriteId resolved once via T1 spriteFor(). SBUF/_C7TAIL are stores,
// not machines: no cls (MachineNode falls back per-tick-safe).
function datumFor(id: string): MachineNodeDatum {
  const cls = MACHINE_META[id]?.cls as SpriteClass | undefined;
  if (cls === undefined) return { label: id, kind: "machine" as const };
  return { label: id, kind: "machine" as const, cls, spriteId: spriteFor(cls) };
}

export const EXPECTED_NODE_COUNT = 28;

export function assertTopologyCounts(nodeCount: number, edgeCount: number): void {
  if (nodeCount !== EXPECTED_NODE_COUNT || edgeCount !== EXPECTED_EDGE_COUNT) {
    throw new Error(
      `topology count mismatch: expected ${EXPECTED_NODE_COUNT}/${EXPECTED_EDGE_COUNT}, got ${nodeCount}/${edgeCount}`,
    );
  }
}
