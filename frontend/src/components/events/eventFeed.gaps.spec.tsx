import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { EventFeed } from "./EventFeed";
import { MachineEventFeed } from "./MachineEventFeed";
import type { TwinEvent } from "./types";

// FE-11 RED: EventFeed renders an explicit gap row (text + glyph, never
// color alone) wherever covered steps are non-contiguous. Sparse events
// are normal, so markers are driven by the explicit `steps` prop only.
// SSR-rendered (no jsdom in this repo).

const HERE = dirname(fileURLToPath(import.meta.url));

function blockEvent(t: number, machine = "B2"): TwinEvent {
  return { event: "BLOCK_ON", t, machine, detail: {} };
}

describe("EventFeed gap rows", () => {
  it("inserts a text+glyph gap row for skipped steps", () => {
    // Given: events at t=0,1,10 with covered steps 0,1,10 (2..9 missing)
    const events = [blockEvent(0), blockEvent(1), blockEvent(10)];
    const steps = [0, 1, 10];
    // When: rendering with the covered steps
    const html = renderToStaticMarkup(<EventFeed events={events} steps={steps} />);
    // Then: one explicit gap row naming the missing range
    expect(html).toContain('data-testid="feed-gap"');
    expect(html).toContain("⚠");
    expect(html).toContain("gap");
    expect(html).toContain("steps 2–9");
    // Then: the marker sits between the t=1 and t=10 rows
    const t1 = html.indexOf("t=1");
    const gap = html.indexOf('data-testid="feed-gap"');
    const t10 = html.indexOf("t=10");
    expect(t1).toBeGreaterThanOrEqual(0);
    expect(gap).toBeGreaterThan(t1);
    expect(t10).toBeGreaterThan(gap);
  });

  it("renders no gap rows without steps", () => {
    // Given: sparse events but no covered-step signal
    const events = [blockEvent(0), blockEvent(1), blockEvent(10)];
    // When: rendering with no steps prop (sparse events are normal)
    const html = renderToStaticMarkup(<EventFeed events={events} />);
    // Then: current behavior preserved, no markers
    expect(html).not.toContain("feed-gap");
  });

  it("renders no gap rows for dense steps", () => {
    // Given: events matching dense steps
    const events = [blockEvent(0), blockEvent(1), blockEvent(2)];
    // When: rendering with dense covered steps
    const html = renderToStaticMarkup(
      <EventFeed events={events} steps={[0, 1, 2]} />,
    );
    // Then: no markers
    expect(html).not.toContain("feed-gap");
  });

  it("caps events but still marks gaps inside the visible window", () => {
    // Given: 12 dense events then a jump, rendered with a small cap
    const events = Array.from({ length: 12 }, (_, t) => blockEvent(t));
    const steps = [...Array.from({ length: 12 }, (_, t) => t), 20];
    // When: rendering capped to the latest 10 rows
    const html = renderToStaticMarkup(
      <EventFeed events={[...events, blockEvent(20)]} steps={steps} cap={10} />,
    );
    // Then: overflow still counts events only, gap marker still present
    expect(html).toContain("…+3 more");
    expect(html).toContain('data-testid="feed-gap"');
  });

  it("MachineEventFeed forwards steps to gap rows", () => {
    // Given: per-machine feed with a step hole (1..4 missing)
    const events = [blockEvent(0), blockEvent(5)];
    // When: rendering the pinned feed with covered steps
    const html = renderToStaticMarkup(
      <MachineEventFeed events={events} machineId="B2" steps={[0, 5]} />,
    );
    // Then: the gap row renders in the pinned feed too
    expect(html).toContain('data-testid="feed-gap"');
    expect(html).toContain("steps 1–4");
  });
});

describe("feed gap styling contract (static CSS)", () => {
  const css = readFileSync(resolve(HERE, "feed-gaps.css"), "utf8");

  it("pairs color with shape/text and freezes under reduced motion", () => {
    expect(css).toContain(".feed-gap-row");
    expect(css).toContain("dashed");
    expect(css).toContain("@media (prefers-reduced-motion: reduce)");
    const tail = css.slice(css.indexOf("@media (prefers-reduced-motion: reduce)"));
    expect(tail).toContain("animation: none");
  });
});
