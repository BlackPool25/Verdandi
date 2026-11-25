/**
 * FE-6: unknown-event surfacing spec (TDD). Unknown channel-7 families must
 * render as explicit states (warn + count indicator), never silently dropped
 * and never rendered as OK. The dossier consumes `summarizeFeedAnomalies`
 * verbatim (shape coordination only — no dossier rewrite here).
 */
import { describe, expect, it, vi, beforeEach } from "vitest";
import {
  capFeed,
  countUnknown,
  familyOf,
  filterEvents,
  isUnknownEvent,
  labelFor,
  resetFeedWarnings,
  summarizeFeedAnomalies,
  UNKNOWN_FAMILY,
  unknownNames,
  warnUnknown,
} from "./feed";
import type { TwinEvent } from "./types";

const KNOWN = { event: "BLOCK_ON", t: 1, machine: "C6", detail: {} } as TwinEvent;
const ODD = { event: "OVERHEAT", t: 2, machine: "B2", detail: {} } as TwinEvent;
const WEIRD = { event: "MELTDOWN", t: 3, machine: "A7", detail: {} } as TwinEvent;

beforeEach(() => {
  resetFeedWarnings();
});

describe("familyOf / isUnknownEvent (no silent catch)", () => {
  it("maps known names to their family", () => {
    expect(familyOf(KNOWN)).toBe("BLOCK");
    expect(isUnknownEvent(KNOWN)).toBe(false);
  });

  it("maps unknown names to UNKNOWN instead of throwing", () => {
    expect(familyOf(ODD)).toBe(UNKNOWN_FAMILY);
    expect(isUnknownEvent(ODD)).toBe(true);
  });
});

describe("countUnknown / unknownNames", () => {
  it("counts unknown rows and lists distinct names sorted", () => {
    expect(countUnknown([KNOWN, ODD, WEIRD, ODD])).toBe(3);
    expect(unknownNames([KNOWN, WEIRD, ODD, WEIRD])).toEqual(["MELTDOWN", "OVERHEAT"]);
    expect(countUnknown([KNOWN])).toBe(0);
    expect(unknownNames([])).toEqual([]);
  });
});

describe("warnUnknown (warn, never silent)", () => {
  it("warns once per unknown name and returns the unknown row count", () => {
    const spy = vi.spyOn(console, "warn").mockImplementation(() => {});
    try {
      expect(warnUnknown([KNOWN, ODD], "test")).toBe(1);
      expect(spy).toHaveBeenCalledTimes(1);
      expect(spy.mock.calls[0]?.[0]).toContain("OVERHEAT");
      // Same names again: no repeat warn, count still reported.
      expect(warnUnknown([ODD], "test")).toBe(1);
      expect(spy).toHaveBeenCalledTimes(1);
      // New name warns again with the fresh name.
      expect(warnUnknown([WEIRD], "test")).toBe(1);
      expect(spy).toHaveBeenCalledTimes(2);
      expect(spy.mock.calls[1]?.[0]).toContain("MELTDOWN");
    } finally {
      spy.mockRestore();
    }
  });

  it("stays quiet when nothing is unknown", () => {
    const spy = vi.spyOn(console, "warn").mockImplementation(() => {});
    try {
      expect(warnUnknown([KNOWN], "test")).toBe(0);
      expect(spy).not.toHaveBeenCalled();
    } finally {
      spy.mockRestore();
    }
  });
});

describe("filterEvents with UNKNOWN family", () => {
  const evs = [KNOWN, ODD, WEIRD] as readonly TwinEvent[];

  it("UNKNOWN family isolates exactly the unknown rows", () => {
    expect(filterEvents(evs, { family: UNKNOWN_FAMILY })).toEqual([ODD, WEIRD]);
  });

  it("a known family excludes unknowns without throwing", () => {
    expect(() => filterEvents(evs, { family: "BLOCK" })).not.toThrow();
    expect(filterEvents(evs, { family: "BLOCK" })).toEqual([KNOWN]);
  });

  it("no family filter keeps every row (unknowns never silently dropped)", () => {
    expect(filterEvents(evs, {})).toHaveLength(3);
  });
});

describe("labelFor unknown tag", () => {
  it("unknown rows carry the ! UNKNOWN tag (color never alone)", () => {
    expect(labelFor(ODD)).toContain("! UNKNOWN");
  });

  it("known rows keep their existing labels", () => {
    expect(labelFor(KNOWN)).toBe("BLOCK_ON C6 t1");
  });
});

describe("summarizeFeedAnomalies (dossier coordination shape)", () => {
  it("reports totals, unknowns, overflow, and no mismatch on a clean feed", () => {
    const evs = [KNOWN, ODD] as readonly TwinEvent[];
    const capped = capFeed(evs, 100);
    const s = summarizeFeedAnomalies(evs, capped.visible, capped.overflow);
    expect(s).toEqual({
      total: 2,
      visible: 2,
      overflow: 0,
      unknownCount: 1,
      unknownNames: ["OVERHEAT"],
      countMismatch: false,
    });
  });

  it("flags visible+overflow vs total drift as an explicit mismatch state", () => {
    const evs = [KNOWN, ODD, WEIRD] as readonly TwinEvent[];
    const s = summarizeFeedAnomalies(evs, [KNOWN], 1);
    expect(s.countMismatch).toBe(true);
    expect(s.total).toBe(3);
    expect(s.unknownCount).toBe(2);
  });
});
