import { MACHINE_META } from "../components/panels/machineMeta";
import { spriteFor, type MachineNodeDatum, type SpriteClass } from "./types";

// 34 nodes: 32 machines (A0-A9, B0-B9, C0-C7, ASM0/1/2, RWK0) + SBUF + _C7TAIL.
// Roster mirrors src/config.py machine order; SBUF/_C7TAIL mirror the twin's
// AGV-drained stores (twin _TAIL_BUF + SBUF shed).
const MACHINES: readonly string[] = [
  ...Array.from({ length: 10 }, (_, i) => `A${i}`),
  ...Array.from({ length: 10 }, (_, i) => `B${i}`),
  ...Array.from({ length: 8 }, (_, i) => `C${i}`),
  "ASM0",
  "ASM1",
  "ASM2",
  "RWK0",
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

export const EXPECTED_NODE_COUNT = 34;
