// FE-9: drop-count readout next to the row-count badge. SSR-rendered (no
// jsdom in this repo); bridgeBase() reads window.location.search at render,
// so a minimal window stub stands in for the browser.
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { ControlsBar } from "./ControlsBar";
import type { TickSource } from "../../sim/tickSource";

(globalThis as unknown as { window: unknown }).window = {
  location: { search: "" },
};

function stubSource(droppedFrames: number, rowCount: number): TickSource {
  return {
    tick: null,
    panelTick: null,
    events: [],
    connected: true,
    cursor: 5,
    rowCount,
    playing: false,
    totalBytes: 0,
    complete: false,
    reconnecting: false,
    episodeId: "ep-1",
    energy: null,
    episodeHeader: null,
    speed: 1,
    setSpeed: () => {},
    setPlaying: () => {},
    stepTo: () => true,
    rowJson: () => undefined,
    startEpisode: () => {},
    disconnect: () => {},
    reconnect: () => {},
    droppedFrames,
  } as unknown as TickSource;
}

describe("ControlsBar drop-count readout (FE-9)", () => {
  it("surfaces the shared-transport drop count beside the row count", () => {
    const html = renderToStaticMarkup(
      <ControlsBar external={{ source: stubSource(3, 42), onEpisode: () => {} }} />,
    );
    expect(html).toContain('data-testid="row-count">42<');
    expect(html).toContain('data-testid="drop-count">3<');
  });

  it("shows zero drops on a clean stream", () => {
    const html = renderToStaticMarkup(
      <ControlsBar external={{ source: stubSource(0, 7), onEpisode: () => {} }} />,
    );
    expect(html).toContain('data-testid="drop-count">0<');
  });
});
