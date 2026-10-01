import { describe, expect, it } from "vitest";
import { STREAM_MACHINE_ORDER, parseLiveTick, toPatch } from "./streamCodec";

// CH8/CH9 wiring spec (MINIPRO-17): live ticks carry the 26-machine
// topology-A roster plus a per-tick currents row (bridge schema v4).
// Failing-first: roster is 26 (not stale-32) and currents survive parsing.

function mkTick(step: number, current = 7.5) {
  return {
    step,
    states: Array.from({ length: 26 }, () => "RUN"),
    throughput: Array.from({ length: 26 }, () => 1),
    currents: Array.from({ length: 26 }, () => current),
  };
}

describe("parseLiveTick topology-A + currents", () => {
  it("accepts the 26-machine roster", () => {
    expect(STREAM_MACHINE_ORDER).toHaveLength(26);
    expect(parseLiveTick(mkTick(0))).not.toBeNull();
  });

  it("keeps the currents row verbatim", () => {
    const row = parseLiveTick(mkTick(3, 8.25));
    expect(row?.currents).toHaveLength(26);
    expect(row?.currents[0]).toBeCloseTo(8.25, 9);
  });

  it("rejects the stale 32-machine shape", () => {
    expect(
      parseLiveTick({
        step: 0,
        states: Array.from({ length: 32 }, () => "RUN"),
        throughput: Array.from({ length: 32 }, () => 1),
        currents: Array.from({ length: 32 }, () => 7.5),
      }),
    ).toBeNull();
  });

  it("rejects missing currents (bridge schema v4 always sends them)", () => {
    expect(
      parseLiveTick({
        step: 0,
        states: Array.from({ length: 26 }, () => "RUN"),
        throughput: Array.from({ length: 26 }, () => 1),
      }),
    ).toBeNull();
  });

  it("rejects non-finite or negative currents", () => {
    const bad = mkTick(0);
    bad.currents[5] = Number.NaN;
    expect(parseLiveTick(bad)).toBeNull();
    const neg = mkTick(0);
    neg.currents[5] = -1;
    expect(parseLiveTick(neg)).toBeNull();
  });

  it("rejects wrong-length currents", () => {
    const short = mkTick(0);
    short.currents = short.currents.slice(0, 25);
    expect(parseLiveTick(short)).toBeNull();
  });

  it("toPatch still maps states/tput by machine id", () => {
    const row = parseLiveTick(mkTick(7));
    expect(row).not.toBeNull();
    if (row === null) return;
    const patch = toPatch(row);
    expect(patch.step).toBe(7);
    expect(Object.keys(patch.states)).toHaveLength(26);
  });
});
