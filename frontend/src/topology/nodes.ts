import type { MachineNodeDatum } from "./types";

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
  ...MACHINES.map((id) => ({ id, data: { label: id, kind: "machine" as const } })),
  { id: "SBUF", data: { label: "SBUF", kind: "sbuf" as const } },
  { id: "_C7TAIL", data: { label: "_C7TAIL", kind: "c7tail" as const } },
];

export const EXPECTED_NODE_COUNT = 34;
