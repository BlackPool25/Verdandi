import { describe, expect, it } from "vitest";
import {
  findMissingRuns,
  findStepGaps,
  gapRangeLabel,
  missingRunLabel,
  summarizeStepGaps,
} from "./gaps";

// FE-11 RED: explicit gap state wherever steps are non-contiguous.
// Pure step-gap contract shared by StripChart + EventFeed.
describe("findStepGaps", () => {
  it("empty input has no gaps", () => {
    expect(findStepGaps([])).toEqual([]);
  });

  it("dense steps have no gaps", () => {
    expect(findStepGaps([0, 1, 2, 3])).toEqual([]);
  });

  it("single step has no gaps", () => {
    expect(findStepGaps([7])).toEqual([]);
  });

  it("one hole yields one gap bounded by present steps", () => {
    expect(findStepGaps([0, 1, 2, 5, 6])).toEqual([{ from: 2, to: 5 }]);
  });

  it("multiple holes yield multiple gaps in order", () => {
    expect(findStepGaps([0, 3, 4, 9])).toEqual([
      { from: 0, to: 3 },
      { from: 4, to: 9 },
    ]);
  });

  it("tolerates unsorted input with duplicates", () => {
    expect(findStepGaps([5, 4, 1, 0, 1])).toEqual([{ from: 1, to: 4 }]);
  });
});

describe("gapRangeLabel", () => {
  it("names a single missing step", () => {
    expect(gapRangeLabel({ from: 3, to: 5 })).toBe("step 4");
  });

  it("names a missing range", () => {
    expect(gapRangeLabel({ from: 1, to: 4 })).toBe("steps 2–3");
  });
});

describe("summarizeStepGaps", () => {
  it("empty summarizes to empty string", () => {
    expect(summarizeStepGaps([])).toBe("");
  });

  it("single gap names its range", () => {
    expect(summarizeStepGaps([{ from: 2, to: 5 }])).toBe("steps 3–4");
  });

  it("multiple gaps join with semicolons", () => {
    expect(
      summarizeStepGaps([
        { from: 0, to: 3 },
        { from: 4, to: 9 },
      ]),
    ).toBe("steps 1–2; steps 5–8");
  });
});

describe("findMissingRuns", () => {
  it("dense finite series has no runs", () => {
    expect(findMissingRuns(new Float32Array([1, 2, 3]))).toEqual([]);
  });

  it("NaN run is reported with inclusive bounds", () => {
    expect(findMissingRuns(new Float32Array([1, NaN, NaN, 2]))).toEqual([
      { start: 1, end: 2 },
    ]);
  });

  it("non-finite infinities count as missing", () => {
    expect(findMissingRuns([1, Infinity, 2])).toEqual([{ start: 1, end: 1 }]);
  });
});

describe("missingRunLabel", () => {
  it("names a single missing index", () => {
    expect(missingRunLabel({ start: 4, end: 4 })).toBe("step 4");
  });

  it("names a missing index range", () => {
    expect(missingRunLabel({ start: 2, end: 5 })).toBe("steps 2–5");
  });
});
