import { describe, expect, it } from "vitest";
import { Ring } from "./ring";

// FE-14 (PRISSUE-68): Ring push/set must never fail silently.
// A failed write is observable via (a) boolean return, (b) counted error
// surface, and (c) strict throwing variants. TDD spec — written BEFORE fix.
describe("Ring loud failures (FE-14)", () => {
  it("push beyond cap is observable: returns false and counts the drop", () => {
    const r = new Ring(2);
    expect(r.push(1)).toBe(true);
    expect(r.push(2)).toBe(true);
    expect(r.errors).toBe(0);
    // When: buffer is full
    const ok = r.push(3);
    // Then: failure is loud, never a silent drop
    expect(ok).toBe(false);
    expect(r.errors).toBe(1);
    expect(r.dropped).toBe(1);
    expect(r.lastError).toMatch(/full|cap/i);
    // Data already stored is untouched
    expect(Array.from(r.snapshot())).toEqual([1, 2]);
  });

  it("set out of range is observable: returns false and counts the error", () => {
    const r = new Ring(4);
    expect(r.set(0, 10)).toBe(true);
    expect(r.errors).toBe(0);
    expect(r.set(4, 99)).toBe(false);
    expect(r.set(-1, 99)).toBe(false);
    expect(r.errors).toBe(2);
    expect(r.lastError).toMatch(/range/i);
    expect(Array.from(r.snapshot())).toEqual([10]);
  });

  it("non-finite values are rejected loudly, not coerced silently", () => {
    const r = new Ring(4);
    expect(r.push(Number.NaN)).toBe(false);
    expect(r.set(0, Number.POSITIVE_INFINITY)).toBe(false);
    expect(r.errors).toBe(2);
    expect(r.length).toBe(0);
  });

  it("strict variants throw on failure", () => {
    const r = new Ring(1);
    r.pushOrThrow(1);
    expect(() => r.pushOrThrow(2)).toThrow(RangeError);
    expect(() => r.setOrThrow(5, 1)).toThrow(RangeError);
    expect(() => r.setOrThrow(0, Number.NaN)).toThrow(TypeError);
  });

  it("success path is unchanged: true returns, zero errors, data intact", () => {
    const r = new Ring(8);
    expect(r.push(1)).toBe(true);
    expect(r.set(3, 4)).toBe(true);
    expect(r.errors).toBe(0);
    expect(r.lastError).toBeNull();
    const snap = r.snapshot();
    expect(snap[0]).toBe(1);
    expect(snap[3]).toBe(4);
  });

  it("resetErrors clears the counted surface without touching data", () => {
    const r = new Ring(1);
    r.push(1);
    r.push(2);
    expect(r.errors).toBe(1);
    r.resetErrors();
    expect(r.errors).toBe(0);
    expect(r.lastError).toBeNull();
    expect(Array.from(r.snapshot())).toEqual([1]);
  });
});
