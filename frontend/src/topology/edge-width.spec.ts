import { describe, expect, it } from "vitest";
import {
  EXPECTED_EDGE_COUNT,
  PINNED_EDGES,
  bufferIdForEdge,
  widthForUtil,
} from "./edges";
import {
  EDGE_BUFFER_EXPECTATIONS,
  EDGE_COUNT,
  STORELESS_EDGE_IDS,
} from "../test/testConstants";

function byId(id: string) {
  const e = PINNED_EDGES.find((p) => p.id === id);
  if (e === undefined) throw new Error(`edge missing: ${id}`);
  return e;
}

function expectedBufferFor(edgeId: string): string | null {
  if (!(edgeId in EDGE_BUFFER_EXPECTATIONS)) throw new Error(`no expectation for ${edgeId}`);
  return EDGE_BUFFER_EXPECTATIONS[edgeId] ?? null;
}

describe("widthForUtil", () => {
  it("maps util 0..1 to strokeWidth 1..4", () => {
    expect(widthForUtil(0)).toBe(1);
    expect(widthForUtil(1)).toBe(4);
    expect(widthForUtil(0.5)).toBeCloseTo(2.5, 9);
  });

  it("clamps out-of-range and non-finite utils", () => {
    expect(widthForUtil(-0.5)).toBe(1);
    expect(widthForUtil(2)).toBe(4);
    expect(widthForUtil(Number.NaN)).toBe(1);
  });
});

describe("bufferIdForEdge", () => {
  it("line-gap and assembly labels map to their buffer id", () => {
    for (const id of ["e-A0-A1", "e-C6-C7", "e-B2-B7P", "e-ASM0-ASM1", "e-ASM1-INSP0", "e-INSP0-ASM2"]) {
      expect(bufferIdForEdge(byId(id))).toBe(expectedBufferFor(id));
    }
  });

  it("tail-stage GA9/GB9 map; _C7TAIL store edge has no buffer", () => {
    for (const id of ["e-A9-SBUF", "e-B9-SBUF", "e-C7-tail"]) {
      expect(bufferIdForEdge(byId(id))).toBe(expectedBufferFor(id));
    }
  });

  it("agv-drain edges resolve GA9/GB9/SBUF; _C7TAIL drain has no buffer", () => {
    for (const id of ["e-A9-kit", "e-B9-kit", "e-SBUF-kit", "e-tail-kit"]) {
      expect(bufferIdForEdge(byId(id))).toBe(expectedBufferFor(id));
    }
  });

  it("rework back-edge maps to RWK_RET; kitC return has no buffer", () => {
    for (const id of ["e-ASM2-RWK0", "e-RWK0-ASM0"]) {
      expect(bufferIdForEdge(byId(id))).toBe(expectedBufferFor(id));
    }
  });

  it("28 of 31 edges track a buffer; only the 3 storeless edges stay at width 1", () => {
    expect(PINNED_EDGES).toHaveLength(EXPECTED_EDGE_COUNT);
    const mapped = PINNED_EDGES.filter((e) => bufferIdForEdge(e) !== null);
    const flat = PINNED_EDGES.filter((e) => bufferIdForEdge(e) === null);
    expect(mapped).toHaveLength(EDGE_COUNT - STORELESS_EDGE_IDS.length);
    expect(flat.map((e) => e.id).sort()).toEqual([...STORELESS_EDGE_IDS].sort());
  });
});
