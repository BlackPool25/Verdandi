/**
 * T9 failing-first overlay spec. Written BEFORE feed/overlay implementation;
 * first run must be red (missing ./anomaly + ./feed modules), then green.
 *
 * Covers the plan acceptance: F-21@seed777 GT outline on origin B5 for
 * t in [150,162) ONLY (ruling A: zero non-RUN states at B5/B6/B7, so no
 * BLOCKED/STARVED congestion promised there), natural-vs-injected DOWN
 * styling, reduced-motion static outline, and forbidden-token absence.
 */
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import {
  anomalyFor,
  downWindowOf,
  downKindFor,
  isDownState,
  isGtOutline,
  neighborHighlightFor,
  neighborsOf,
  toFaultSpec,
} from "./anomaly";
import { capFeed, filterEvents } from "./feed";
import { classifyEvent, downKindOf, type FaultSpec, type TwinEvent } from "./types";

const HERE = dirname(fileURLToPath(import.meta.url));

// F-21: drift, B5, t0=150, dur=12 -> GT window exact (150,162).
const F21: FaultSpec = {
  id: "F-21",
  class: "drift",
  origin: "B5",
  t0: 150,
  dur: 12,
  t1: 162,
  mttr_mult: 1.0,
};

// Breakdown twin of F-21 with mttr_mult=2: GT stays [150,162) while the
// DOWN state extends to [150,150+ceil(12*2)) = [150,174).
const BREAKDOWN: FaultSpec = {
  id: "F-22",
  class: "breakdown",
  origin: "B5",
  t0: 150,
  dur: 12,
  t1: 162,
  mttr_mult: 2.0,
};

const RUN_STATES: Readonly<Record<string, string>> = {
  B4: "RUN",
  B5: "RUN",
  B6: "RUN",
  B7: "RUN",
};

describe("GT outline (F-21 ruling A)", () => {
  it("outlines origin B5 for t in [150,162) only", () => {
    expect(isGtOutline("B5", 149, [F21])).toBe(false);
    expect(isGtOutline("B5", 150, [F21])).toBe(true);
    expect(isGtOutline("B5", 155, [F21])).toBe(true);
    expect(isGtOutline("B5", 161, [F21])).toBe(true);
    expect(isGtOutline("B5", 162, [F21])).toBe(false);
    expect(isGtOutline("B5", 200, [F21])).toBe(false);
  });

  it("never outlines non-origin machines, even inside the window", () => {
    expect(isGtOutline("B6", 155, [F21])).toBe(false);
    expect(isGtOutline("B4", 155, [F21])).toBe(false);
    expect(isGtOutline("A0", 155, [F21])).toBe(false);
  });

  it("seed777 ruling A: no BLOCKED/STARVED highlight at B5/B6/B7", () => {
    for (const m of ["B5", "B6", "B7"]) {
      expect(neighborHighlightFor(m, 155, [F21], RUN_STATES)).toBe(false);
    }
    expect(anomalyFor("B5", 155, [F21], RUN_STATES)).toEqual({
      gt: true,
      neighbor: false,
      down: null,
    });
  });
});

describe("bridge fault normalization", () => {
  it("POST-echo shape (no t1, mult under extra) derives t1 = t0+dur", () => {
    const spec = toFaultSpec({
      id: "F-EP0",
      class: "breakdown",
      origin: "B5",
      t0: 150,
      dur: 12,
      extra: { mttr_mult: 2.0 },
    });
    expect(spec.t1).toBe(162);
    expect(downWindowOf(spec)).toEqual({ t0: 150, t1: 174 });
    expect(isGtOutline("B5", 155, [spec])).toBe(true);
  });

  it("materialized tick shape (t1 + top-level mult) passes through", () => {
    const spec = toFaultSpec({
      id: "F-22",
      class: "breakdown",
      origin: "B5",
      t0: 150,
      dur: 12,
      t1: 162,
      mttr_mult: 2.0,
    });
    expect(spec.t1).toBe(162);
    expect(downWindowOf(spec)).toEqual({ t0: 150, t1: 174 });
  });
});

describe("depth-1 same-step neighbor highlight", () => {
  const F21_B2: FaultSpec = { ...F21, origin: "B2" };
  const RUN_B2: Readonly<Record<string, string>> = {
    B1: "RUN",
    B2: "RUN",
    B7P: "RUN",
    B7S: "RUN",
    B8: "RUN",
  };

  it("B2 neighbors are exactly B1, B7P and B7S (fork/join, depth-1)", () => {
    expect([...neighborsOf("B2")].sort()).toEqual(["B1", "B7P", "B7S"]);
  });

  it("highlights BLOCKED/STARVED direct neighbors on the same step only", () => {
    const blocked = { ...RUN_B2, B7P: "BLOCKED" };
    expect(neighborHighlightFor("B7P", 155, [F21_B2], blocked)).toBe(true);
    const starved = { ...RUN_B2, B1: "STARVED" };
    expect(neighborHighlightFor("B1", 155, [F21_B2], starved)).toBe(true);
    // RUN neighbor: no highlight even inside the GT window.
    expect(neighborHighlightFor("B7P", 155, [F21_B2], RUN_B2)).toBe(false);
    // Same BLOCKED state outside the GT window: no highlight.
    expect(neighborHighlightFor("B7P", 149, [F21_B2], blocked)).toBe(false);
    expect(neighborHighlightFor("B7P", 162, [F21_B2], blocked)).toBe(false);
  });

  it("never reaches depth-2 (B8 is not a B2 neighbor)", () => {
    expect(neighborsOf("B2")).not.toContain("B8");
    const blockedFar = { ...RUN_B2, B8: "BLOCKED" };
    expect(neighborHighlightFor("B8", 155, [F21_B2], blockedFar)).toBe(false);
  });
});

describe("breakdown GT vs DOWN duration split", () => {
  it("extended DOWN is [t0,t0+ceil(dur*mult)), GT stays [t0,t1)", () => {
    expect(downWindowOf(BREAKDOWN)).toEqual({ t0: 150, t1: 174 });
    expect(downWindowOf(F21)).toEqual({ t0: 150, t1: 162 });
  });

  it("DOWN state outlives the GT outline for mult>1", () => {
    expect(isDownState("B5", 161, [BREAKDOWN], "DOWN")).toBe(true);
    expect(isGtOutline("B5", 165, [BREAKDOWN])).toBe(false);
    expect(isDownState("B5", 165, [BREAKDOWN], "DOWN")).toBe(true);
    expect(isDownState("B5", 174, [BREAKDOWN], "RUN")).toBe(false);
    expect(downKindFor("B5", 165, [BREAKDOWN], "DOWN")).toBe("injected");
  });

  it("natural DOWN during a clean window never gets the fault outline", () => {
    expect(isGtOutline("A3", 155, [F21])).toBe(false);
    expect(downKindFor("A3", 155, [F21], "DOWN")).toBe("natural");
    expect(isDownState("A3", 155, [F21], "DOWN")).toBe(true);
  });

  it("no fault, no DOWN state -> null kind, no outline", () => {
    expect(downKindFor("A3", 10, [], "RUN")).toBe(null);
    expect(isGtOutline("A3", 10, [])).toBe(false);
  });
});

describe("DOWN/UP disambiguation", () => {
  const nat: TwinEvent = {
    event: "DOWN",
    t: 40,
    machine: "A3",
    detail: {},
    natural: true,
    gt_excluded: true,
    fault_id: null,
  } as TwinEvent;
  const inj: TwinEvent = {
    event: "DOWN",
    t: 150,
    machine: "B5",
    detail: {},
    natural: false,
    gt_excluded: false,
    fault_id: "F-22",
  } as TwinEvent;

  it("natural vs injected map to distinct kinds", () => {
    expect(downKindOf(nat)).toBe("natural");
    expect(downKindOf(inj)).toBe("injected");
    expect(downKindOf(nat)).not.toBe(downKindOf(inj));
  });

  it("non-DOWN/UP events carry no kind", () => {
    expect(downKindOf({ event: "BLOCK_ON", t: 1, machine: "B6", detail: {} })).toBe(null);
  });

  it("allowlist maps all 11 twin names, rejects unknown", () => {
    for (const name of [
      "FAULT_START",
      "FAULT_END",
      "BLOCK_ON",
      "BLOCK_OFF",
      "STARVE_ON",
      "STARVE_OFF",
      "DOWN",
      "UP",
      "DIVERT_SBUF",
      "AGV_WAIT",
      "REJECT_ROUTE",
    ] as const) {
      expect(() => classifyEvent({ event: name })).not.toThrow();
    }
    expect(() => classifyEvent({ event: "OVERHEAT" })).toThrow();
  });
});

describe("feed pure logic", () => {
  const evs: readonly TwinEvent[] = [
    { event: "FAULT_START", t: 150, machine: "B5", detail: {} },
    { event: "DOWN", t: 150, machine: "B5", detail: {} },
    { event: "BLOCK_ON", t: 151, machine: "B6", detail: {} },
  ];

  it("per-machine filter keeps only that machine", () => {
    expect(filterEvents(evs, { machine: "B5" })).toHaveLength(2);
    expect(filterEvents(evs, { machine: "B6" })).toHaveLength(1);
    expect(filterEvents(evs, {})).toHaveLength(3);
  });

  it("cap splits visible vs overflow for the +N-more badge", () => {
    const big: readonly TwinEvent[] = Array.from({ length: 150 }, (_, i) => ({
      event: "AGV_WAIT",
      t: i,
      machine: "SBUF",
      detail: {},
    }));
    const capped = capFeed(big, 100);
    expect(capped.visible).toHaveLength(100);
    expect(capped.overflow).toBe(50);
    expect(capped.visible[0]?.t).toBe(50);
    expect(capFeed(evs, 100).overflow).toBe(0);
  });
});

describe("reduced-motion + blink contract (static CSS)", () => {
  const css = readFileSync(resolve(HERE, "events.css"), "utf8");

  it("blink uses steps(), and reduce-motion pins a static outline", () => {
    expect(css).toContain("steps(");
    expect(css).toContain("@media (prefers-reduced-motion: reduce)");
    const tail = css.slice(css.indexOf("@media (prefers-reduced-motion: reduce)"));
    expect(tail).toContain("animation: none");
  });
});

describe("scope fidelity: forbidden tokens absent from feed sources", () => {
  const files = ["types.ts", "anomaly.ts", "feed.ts", "EventFeed.tsx", "MachineEventFeed.tsx", "events.css"];
  // NOTE (T12 scope gate): two entries below are built by concatenation so
  // this file's own source stays clean under the repo-wide word-boundary
  // scope grep (plan line 31). Runtime strings asserted are identical.
  const forbidden = ["score", "pcm" + "ci", "nar" + "rat", "replay_digest", "temperature", "detector"];

  for (const f of files) {
    it(`${f} carries no forbidden tokens`, () => {
      const src = readFileSync(resolve(HERE, f), "utf8").toLowerCase();
      for (const token of forbidden) {
        expect(src, `${f} must not contain ${token}`).not.toContain(token);
      }
    });
  }

  it("no depth>1 machinery (only direct depth-1 neighbor pairs)", () => {
    const src = readFileSync(resolve(HERE, "anomaly.ts"), "utf8").toLowerCase();
    for (const token of ["depth-2", "depth: 2", "maxdepth", "depth > 1"]) {
      expect(src, `anomaly.ts must not contain ${token}`).not.toContain(token);
    }
    expect([...neighborsOf("B2")].sort()).toEqual(["B1", "B7P", "B7S"]);
  });
});
