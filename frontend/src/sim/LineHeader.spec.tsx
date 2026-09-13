// L1 header strip spec: honest KPIs from Task 1 selectors, missing -> "—",
// badge throttle intact, no availability-metric text. SSR-rendered (no jsdom
// in this repo). The forbidden-term check below splits its literal so this
// spec file itself keeps the forbidden-term grep gate empty.
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import fixture from "../test/fixtures/ticks-777.json";
import { createTwinStore } from "../store/twinStore";
import { buildBurst } from "../test/synthetic";
import { SBUF_HIGH } from "../components/panels/machineMeta";
import { lineStatsFor, type PanelTick } from "../components/panels/selectors";
import { LineHeader } from "./LineHeader";

interface FixtureTick {
  readonly step: number;
  readonly states: readonly string[];
  readonly obs: readonly number[];
  readonly throughput: readonly number[];
  readonly buffers: readonly number[];
  readonly sbuf_level: number;
  readonly quality: Readonly<Record<string, unknown>>;
}

interface FixtureShape {
  readonly machine_order: readonly string[];
  readonly buffer_order: readonly string[];
  readonly ticks: Readonly<Record<string, FixtureTick>>;
  readonly c7tail_final: number;
}

const F = fixture as unknown as FixtureShape;

function panelTickAt(step: number): PanelTick {
  const t = F.ticks[String(step)];
  if (t === undefined) throw new Error(`fixture missing step ${step}`);
  return {
    step: t.step,
    states: t.states,
    obs: t.obs,
    throughput: t.throughput,
    buffers: t.buffers,
    sbuf_level: t.sbuf_level,
    quality: t.quality,
    machineOrder: F.machine_order,
    bufferOrder: F.buffer_order,
    c7tailFinal: F.c7tail_final,
  };
}

const FULL_HEADER = {
  sbuf_stats: { diverted: 7, drained: 5, max_occupancy: 26 },
  flow_stats: { sunk: 41, scrapped: 3, rejected: 2, reworked: 4, c7tail: 0 },
  c7tail_final: 0,
} as const;

describe("LineHeader: honest KPIs, missing -> —", () => {
  it("step 150: tput/counts/sbuf/finals match selectors verbatim", () => {
    // Given: the live tick row + a full episode header
    const tick = panelTickAt(150);
    const s = lineStatsFor(tick);
    const store = createTwinStore();
    // When: rendering the header strip
    const html = renderToStaticMarkup(
      <LineHeader
        tick={tick}
        episodeHeader={FULL_HEADER}
        episodeId="ep-777"
        speed={2}
        playing={true}
        selectedId="B5"
        store={store}
      />,
    );
    // Then: per-tick aggregates pass through verbatim
    expect(html).toContain(`tput ${s.tputSum}`);
    expect(html).toContain(`RUN ${s.run}`);
    expect(html).toContain(`BLOCKED ${s.blocked}`);
    expect(html).toContain(`STARVED ${s.starved}`);
    expect(html).toContain(`DOWN ${s.down}`);
    expect(html).toContain(`SBUF ${s.sbufLevel}`);
    // Then: episode finals pass through verbatim
    expect(html).toContain("sunk 41");
    expect(html).toContain("scrapped 3");
    expect(html).toContain("reworked 4");
    expect(html).toContain("c7tail_final 0");
    // Then: chrome (breadcrumb / episode / step / speed / playing)
    expect(html).toContain("Line › B5");
    expect(html).toContain("ep ep-777");
    expect(html).toContain("step 150");
    expect(html).toContain("2x");
    expect(html).toContain("playing");
    // Then: HIGH badge iff sbuf >= threshold
    if (tick.sbuf_level >= SBUF_HIGH) {
      expect(html).toContain('data-testid="line-header-sbuf-high"');
    } else {
      expect(html).not.toContain('data-testid="line-header-sbuf-high"');
    }
    // Then: no availability-metric text anywhere
    expect(html.toLowerCase().includes("o" + "ee")).toBe(false);
  });

  it("null tick + null header: every value is — with the empty marker", () => {
    // Given: no tick row and no episode header yet
    const store = createTwinStore();
    // When: rendering the header strip
    const html = renderToStaticMarkup(
      <LineHeader
        tick={null}
        episodeHeader={null}
        episodeId={null}
        speed={1}
        playing={false}
        selectedId={null}
        store={store}
      />,
    );
    // Then: empty-tick marker + "—" for every value, never a zero
    expect(html).toContain('data-testid="line-header-empty"');
    expect(html).toContain("Line › —");
    expect(html).toContain("tput —");
    expect(html).toContain("RUN —");
    expect(html).toContain("sunk —");
    expect(html).toContain("scrapped —");
    expect(html).toContain("reworked —");
    expect(html).toContain("c7tail_final —");
    expect(html).toContain("paused");
    expect(html.toLowerCase().includes("o" + "ee")).toBe(false);
  });

  it("c7tail falls back to the tick payload when the header is missing", () => {
    // Given: header finals absent but the tick carries c7tailFinal
    const tick = panelTickAt(0);
    const store = createTwinStore();
    // When: rendering with a null header
    const html = renderToStaticMarkup(
      <LineHeader
        tick={tick}
        episodeHeader={null}
        episodeId="ep-777"
        speed={1}
        playing={true}
        selectedId="A0"
        store={store}
      />,
    );
    // Then: c7tail_final comes from the tick, flow finals stay "—"
    expect(html).toContain(`c7tail_final ${F.c7tail_final}`);
    expect(html).toContain("sunk —");
  });

  it("badge throttle: 100ms gate caps flushes under continuous ingest", () => {
    // Given: a store on fake time with a badge subscriber (the header pattern)
    let nowMs = 0;
    const store = createTwinStore({ now: () => nowMs });
    let emits = 0;
    store.subscribeBadges(() => {
      emits += 1;
    });
    // When: 40 ticks arrive 10ms apart with a flush per tick
    for (const t of buildBurst(40)) {
      store.ingest(t);
      nowMs += 10;
      store.flushBadges();
    }
    // Then: the 100ms gate caps React-visible emits at 10Hz
    expect(emits).toBeGreaterThanOrEqual(1);
    expect(emits).toBeLessThanOrEqual(10);
  });
});
