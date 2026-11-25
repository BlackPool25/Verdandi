// FE-4: single home for the machine/topology literals previously hardcoded
// across the spec files. Pure refactor: every value below is copied verbatim
// from the specs it replaces, so assertions are byte-identical.
// Source of truth for SBUF cap/threshold stays in machineMeta (re-exported
// here so specs import from exactly one place).
export { SBUF_CAP, SBUF_HIGH } from "../components/panels/machineMeta";

// Topology-A census (matches EXPECTED_* in topology/edges + topology/nodes).
export const MACHINE_COUNT = 26;
export const NODE_COUNT = 28;
export const EDGE_COUNT = 31;

// Frozen-fixture probe steps (seed 777): first / live / last sparse rows.
export const PROBED_STEPS = [0, 150, 299] as const;
export const FIRST_STEP = 0;
export const LIVE_STEP = 150;
export const FINAL_STEP = 299;

// Special node ids.
export const SBUF_ID = "SBUF";
export const C7TAIL_ID = "_C7TAIL";
export const UNKNOWN_MACHINE_ID = "ZZZ";

// SBUF high-util threshold: cap 30 * 80% <=> level >= 24.
export const SBUF_HIGH_LEVEL = 24;

// One probe machine per panel class (config Table 3.1 classes).
export const CLASS_PROBES: Readonly<Record<string, string>> = {
  feed: "A0",
  form: "A1",
  process: "B2",
  finish: "A8",
  "inspect-tail": "A9",
  "assembly-kit": "ASM0",
  "assembly-join": "ASM1",
  test: "ASM2",
  rework: "RWK0",
};

// L4 faceplate rail: exactly the 9 class-probe ids rendered in order.
export const FACEPLATE_IDS_EXPECTED: readonly string[] = [
  "A0",
  "A2",
  "A8",
  "A9",
  "B2",
  "C7",
  "ASM1",
  "ASM2",
  "RWK0",
];

// Tail-path routing probes.
export const AGV_TAILS: readonly string[] = ["A9", "B9", "C7"];
export const NEVER_DIVERTS: readonly string[] = ["A0", "B1", "C1"];
export const SBUF_ELIGIBLE_PROBES: readonly string[] = ["B2", "RWK0"];

// Topology roster deltas vs the retired v1 roster.
export const DROPPED_MACHINES: readonly string[] = [
  "A3",
  "A4",
  "A5",
  "A6",
  "B3",
  "B4",
  "B5",
  "B6",
  "B7",
  "C3",
  "C4",
  "C5",
];
export const ADDED_MACHINES: readonly string[] = [
  "B7P",
  "B7S",
  "PKG0",
  "PKG1",
  "PKG2",
  "INSP0",
];

// Pinned-edge class census: line-gap 16 + tail-stage 4 + agv-drain 4 +
// assembly 3 + rework 2 + packaging 2 = 31.
export const EDGE_CLASS_CENSUS: Readonly<Record<string, number>> = {
  "line-gap": 16,
  "tail-stage": 4,
  "agv-drain": 4,
  assembly: 3,
  rework: 2,
  packaging: 2,
};

// Rework cycle back-edge source (ASM2 -> RWK0).
export const REWORK_BACK_SOURCE = "ASM2";

// Edges with no buffer (stay at width 1 while mapped edges move).
export const STORELESS_EDGE_IDS: readonly string[] = [
  "e-C7-tail",
  "e-RWK0-ASM0",
  "e-tail-kit",
];

// Edge id -> expected buffer id (null = storeless), per bufferIdForEdge.
export const EDGE_BUFFER_EXPECTATIONS: Readonly<Record<string, string | null>> = {
  "e-A0-A1": "A01",
  "e-C6-C7": "C67",
  "e-B2-B7P": "B2B7P",
  "e-ASM0-ASM1": "ASM01",
  "e-ASM1-INSP0": "INSP01",
  "e-INSP0-ASM2": "INSP02",
  "e-A9-SBUF": "GA9",
  "e-B9-SBUF": "GB9",
  "e-C7-tail": null,
  "e-A9-kit": "GA9",
  "e-B9-kit": "GB9",
  "e-SBUF-kit": "SBUF",
  "e-tail-kit": null,
  "e-ASM2-RWK0": "RWK_RET",
  "e-RWK0-ASM0": null,
};

export const SBUF_KIT_EDGE_ID = "e-SBUF-kit";

// _C7TAIL panel label (no per-step series exists for the tail aggregate).
export const NO_SERIES_LABEL = "no per-step series";

// Stale-state guard probe: reselecting the same machine returns equal values.
export const STALE_GUARD_ID = "B7P";

// Arbitrary buffer id for the TickPatch optional-buffers unit check.
export const SAMPLE_BUFFER_ID = "A01";
