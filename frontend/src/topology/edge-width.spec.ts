import { describe, expect, it } from "vitest";
import {
  EXPECTED_EDGE_COUNT,
  PINNED_EDGES,
  bufferIdForEdge,
  widthForUtil,
} from "./edges";

function byId(id: string) {
  const e = PINNED_EDGES.find((p) => p.id === id);
  if (e === undefined) throw new Error(`edge missing: ${id}`);
  return e;
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
    expect(bufferIdForEdge(byId("e-A0-A1"))).toBe("A01");
    expect(bufferIdForEdge(byId("e-C6-C7"))).toBe("C67");
    expect(bufferIdForEdge(byId("e-B2-B7P"))).toBe("B2B7P");
    expect(bufferIdForEdge(byId("e-ASM0-ASM1"))).toBe("ASM01");
    expect(bufferIdForEdge(byId("e-ASM1-INSP0"))).toBe("INSP01");
    expect(bufferIdForEdge(byId("e-INSP0-ASM2"))).toBe("INSP02");
  });

  it("tail-stage GA9/GB9 map; _C7TAIL store edge has no buffer", () => {
    expect(bufferIdForEdge(byId("e-A9-SBUF"))).toBe("GA9");
    expect(bufferIdForEdge(byId("e-B9-SBUF"))).toBe("GB9");
    expect(bufferIdForEdge(byId("e-C7-tail"))).toBeNull();
  });

  it("agv-drain edges resolve GA9/GB9/SBUF; _C7TAIL drain has no buffer", () => {
    expect(bufferIdForEdge(byId("e-A9-kit"))).toBe("GA9");
    expect(bufferIdForEdge(byId("e-B9-kit"))).toBe("GB9");
    expect(bufferIdForEdge(byId("e-SBUF-kit"))).toBe("SBUF");
    expect(bufferIdForEdge(byId("e-tail-kit"))).toBeNull();
  });

  it("rework back-edge maps to RWK_RET; kitC return has no buffer", () => {
    expect(bufferIdForEdge(byId("e-ASM2-RWK0"))).toBe("RWK_RET");
    expect(bufferIdForEdge(byId("e-RWK0-ASM0"))).toBeNull();
  });

  it("28 of 31 edges track a buffer; only the 3 storeless edges stay at width 1", () => {
    expect(PINNED_EDGES).toHaveLength(EXPECTED_EDGE_COUNT);
    const mapped = PINNED_EDGES.filter((e) => bufferIdForEdge(e) !== null);
    const flat = PINNED_EDGES.filter((e) => bufferIdForEdge(e) === null);
    expect(mapped).toHaveLength(28);
    expect(flat.map((e) => e.id).sort()).toEqual(
      ["e-C7-tail", "e-RWK0-ASM0", "e-tail-kit"].sort(),
    );
  });
});
