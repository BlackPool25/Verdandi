import { describe, expect, it } from "vitest";
import { createTwinStore } from "../store/twinStore";
import { buildBurst, faultStormBurst } from "./synthetic";

// Perf contract (plan checkbox 5): graph chrome must not re-render per tick.
// Canvas paints via transient subscribe + rAF; React badges at 4-10Hz.
describe("render-counter: graph chrome stays at 0 renders per tick", () => {
  it("ingests a 300-tick seed-777 burst with zero chrome renders and >0 paints", () => {
    let nowMs = 0;
    const store = createTwinStore({ now: () => nowMs });
    // Given: graph chrome binds ONLY to the badge snapshot (React state at
    // 4-10Hz); the canvas loop binds transiently per tick (refs, no setState)
    let chromeRenders = 0;
    const unsubChrome = store.subscribeBadges(() => {
      chromeRenders += 1;
    });
    let paints = 0;
    const unsubPaint = store.subscribeTransient(() => {
      paints += 1;
      store.paintDirty();
    });

    // When: 300-tick burst at 1x virtual time (250ms per tick), no badge flush
    const ticks = buildBurst(300);
    const lat: number[] = [];
    for (const t of ticks) {
      const t0 = performance.now();
      store.ingest(t);
      lat.push(performance.now() - t0);
      nowMs += 250;
    }

    // Then: chrome never re-rendered per tick; canvas painted; cursor intact
    expect(chromeRenders).toBe(0);
    expect(paints).toBe(300);
    expect(store.cursor()).toBe(299);
    expect(store.backpressure()).toBe(0);
    expect(store.paintCount()).toBeGreaterThan(0);
    // One badge flush emits exactly one chrome render (not 300)
    store.flushBadges();
    expect(chromeRenders).toBe(1);
    unsubChrome();
    unsubPaint();
    const p95 = percentile(lat, 95);
    console.log(`t5-p95-1x-ms=${p95.toFixed(3)} paints=${paints}`);
    expect(p95).toBeLessThanOrEqual(100);
  });

  it("4x stream keeps p95 tick-to-paint within 200ms", () => {
    let nowMs = 0;
    const store = createTwinStore({ now: () => nowMs });
    let paints = 0;
    store.subscribeTransient(() => {
      paints += 1;
      store.paintDirty();
    });
    const ticks = buildBurst(300);
    const lat: number[] = [];
    for (const t of ticks) {
      const t0 = performance.now();
      store.ingest(t);
      lat.push(performance.now() - t0);
      nowMs += 62.5; // 4x: 16 steps/s
      if (t.step % 4 === 0) store.flushBadges();
    }
    store.flushBadges();
    const p95 = percentile(lat, 95);
    console.log(`t5-p95-4x-ms=${p95.toFixed(3)} paints=${paints}`);
    expect(paints).toBeGreaterThan(0);
    expect(p95).toBeLessThanOrEqual(200);
  });

  it("fault-storm burst increments backpressure without losing the cursor", () => {
    let nowMs = 0;
    const store = createTwinStore({ now: () => nowMs, frameBudget: 8 });
    // When: fault storm delivered as one synchronous burst while rAF is
    // starved (no paint between ticks), then a single paint catches up
    for (const t of faultStormBurst(120)) store.ingest(t);
    store.paintDirty();
    store.flushBadges();
    // Then: cursor intact, backpressure counted, rings hold the tail
    expect(store.cursor()).toBe(119);
    expect(store.backpressure()).toBeGreaterThan(0);
    const tail = store.series("A5");
    expect(tail.length).toBeGreaterThan(0);
    const last = tail[tail.length - 1];
    if (last === undefined) throw new Error("empty A5 tail");
    expect(Number.isFinite(last)).toBe(true);
  });

  it("second identical burst reproduces the same rings (no stale state)", () => {
    let nowMs = 0;
    const first = createTwinStore({ now: () => nowMs });
    for (const t of buildBurst(300)) {
      first.ingest(t);
      nowMs += 250;
    }
    const snapA = Array.from(first.series("B5"));
    const second = createTwinStore({ now: () => nowMs });
    for (const t of buildBurst(300)) second.ingest(t);
    expect(Array.from(second.series("B5"))).toEqual(snapA);
  });

  it("stopping a burst mid-way leaves rings consistent", () => {
    let nowMs = 0;
    const store = createTwinStore({ now: () => nowMs });
    const ticks = buildBurst(300);
    for (const t of ticks.slice(0, 150)) {
      store.ingest(t);
      nowMs += 250;
    }
    // cancel/resume probe: stop at 150, then resume the rest
    expect(store.cursor()).toBe(149);
    expect(store.series("C3").length).toBe(150);
    for (const t of ticks.slice(150)) {
      store.ingest(t);
      nowMs += 250;
    }
    expect(store.cursor()).toBe(299);
    expect(store.series("C3").length).toBe(300);
  });

  it("badges throttle to 4-10Hz under continuous ingest", () => {
    let nowMs = 0;
    const store = createTwinStore({ now: () => nowMs });
    let badgeEmits = 0;
    store.subscribeBadges(() => {
      badgeEmits += 1;
    });
    // 10s of 1x stream (40 ticks x 250ms), flush attempted every tick.
    // Stream-limited: every tick passes the 100ms gate -> 40 emits = 4Hz.
    for (const t of buildBurst(40)) {
      store.ingest(t);
      nowMs += 250;
      store.flushBadges();
    }
    // Offer-limited: 40 ticks x 10ms = 0.4s stream, throttle caps at 10Hz.
    let fastEmits = 0;
    const store2 = createTwinStore({ now: () => nowMs });
    store2.subscribeBadges(() => {
      fastEmits += 1;
    });
    for (const t of buildBurst(40)) {
      store2.ingest(t);
      nowMs += 10;
      store2.flushBadges();
    }
    console.log(`t5-badge-emits-1x10s=${badgeEmits} t5-badge-emits-fast04s=${fastEmits}`);
    expect(badgeEmits).toBe(40);
    expect(fastEmits).toBeGreaterThanOrEqual(1);
    expect(fastEmits).toBeLessThanOrEqual(10);
  });
});

function percentile(xs: readonly number[], p: number): number {
  if (xs.length === 0) return 0;
  const s = [...xs].sort((a, b) => a - b);
  const i = Math.min(s.length - 1, Math.ceil((p / 100) * s.length) - 1);
  const v = s[Math.max(0, i)];
  return v ?? 0;
}
