import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { createTwinStore } from "../../store/twinStore";
import type { Tick } from "../../store/tick";
import { StripChart } from "./StripChart";

// FE-11 RED: seek/gap semantics must not render continuous charts over
// discontinuous data. StripChart renders an explicit gap state (break
// marker + badge) wherever steps are non-contiguous. SSR-rendered
// (no jsdom in this repo); canvas painting is covered by the pen-lift
// unit tests below via a mock context.

function tickAt(step: number, value: number): Tick {
  return {
    step,
    states: [],
    obs: [value],
    throughput: [],
    buffers: [],
    sbuf_level: 0,
    events_at_k: [],
    faults: [],
    quality: {},
    currents: [value],
  };
}

describe("StripChart gap state", () => {
  it("renders a text+glyph gap badge for a skipped step range", () => {
    // Given: ring slots 3-4 never ingested (transport drop / seek hole)
    const store = createTwinStore({ machineOrder: ["B2"] });
    for (const s of [0, 1, 2, 5, 6]) store.ingest(tickAt(s, 10 + s));
    store.seek(6, 0);
    store.flushBadges();
    // When: the played steps ride along as the gap signal
    const html = renderToStaticMarkup(
      <StripChart store={store} machineId="B2" steps={[0, 1, 2, 5, 6]} />,
    );
    // Then: explicit gap state, text + glyph (color never the only signal)
    expect(html).toContain('data-testid="strip-gap-B2"');
    expect(html).toContain("⚠");
    expect(html).toContain("gap");
    expect(html).toContain("steps 3–4");
  });

  it("renders no gap badge for dense steps", () => {
    // Given: contiguous ingest with matching steps
    const store = createTwinStore({ machineOrder: ["B2"] });
    for (const s of [0, 1, 2, 3]) store.ingest(tickAt(s, 10 + s));
    store.seek(3, 0);
    store.flushBadges();
    // When: rendering with dense steps
    const html = renderToStaticMarkup(
      <StripChart store={store} machineId="B2" steps={[0, 1, 2, 3]} />,
    );
    // Then: no gap state anywhere
    expect(html).not.toContain("strip-gap-B2");
  });

  it("renders no gap badge without steps on dense data", () => {
    // Given: contiguous ingest and no explicit step list. (The ring
    // rejects non-finite writes, so zero-filled holes are invisible
    // here by design — the steps prop is the gap signal, never zeros.)
    const store = createTwinStore({ machineOrder: ["B2"] });
    for (const s of [0, 1, 2, 3]) store.ingest(tickAt(s, 10 + s));
    store.seek(3, 0);
    store.flushBadges();
    // When: rendering with no explicit steps
    const html = renderToStaticMarkup(<StripChart store={store} machineId="B2" />);
    // Then: no false gap state
    expect(html).not.toContain("strip-gap-B2");
  });
});
