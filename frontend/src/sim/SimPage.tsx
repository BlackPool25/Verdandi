import { useEffect, useMemo, useRef, useState } from "react";
import { ControlsBar } from "../components/controls/ControlsBar";
import { postEpisode } from "../components/controls/api";
import { EventFeed } from "../components/events/EventFeed";
import { toFaultSpec } from "../components/events/anomaly";
import type { FaultSpec } from "../components/events/types";
import { createTwinStore } from "../store/twinStore";
import type { Tick } from "../store/tick";
import {
  BufferBars,
  Legends,
  MachinePanel,
} from "../components/panels";
import { STREAM_MACHINE_ORDER, useTickSource } from "./tickSource";
import { LineHeader } from "./LineHeader";
import { BUFFER_IDS } from "../store/tick";
import { TopologyView } from "../topology/TopologyView";
import "./simShell.css";

// /sim route: ReactFlow topology + ControlsBar + T8 panels on ONE shared
// tickSource. Single episode + single EventSource: episode creation (auto
// seed on mount, or ControlsBar) feeds useTickSource, and topology/panels/
// controls all render its playback cursor — never divergent streams.
function initialSelection(): string | null {
  try {
    return new URLSearchParams(window.location.search).get("probe");
  } catch {
    return null;
  }
}

function initialSeed(): number {
  try {
    const raw = Number(new URLSearchParams(window.location.search).get("seed") ?? "777");
    return Number.isInteger(raw) && raw >= 0 ? raw : 777;
  } catch {
    return 777;
  }
}

function initialEpisode(): string | null {
  try {
    return new URLSearchParams(window.location.search).get("episode");
  } catch {
    return null;
  }
}

// Pixel-style loading skeleton: static block bars on 8px multiples, hard
// edges, no animation (stays static under prefers-reduced-motion).
function SimSkeleton(): React.JSX.Element {
  return (
    <section data-testid="sim-skeleton" aria-label="loading episode" className="sim-box sim-shell__full">
      <h2 className="px-h2">Loading episode…</h2>
      <div className="sim-skel-bar" style={{ width: 256 }} />
      <div className="sim-skel-bar" style={{ width: 192 }} />
      <div className="sim-skel-bar" style={{ width: 224 }} />
    </section>
  );
}

export function SimPage(): React.JSX.Element {
  const [episodeId, setEpisodeId] = useState<string | null>(() => initialEpisode());
  const [seedError, setSeedError] = useState(false);
  const source = useTickSource({ episodeId });
  const [selectedId, setSelectedId] = useState<string | null>(initialSelection);
  const [chartStore] = useState(() =>
    createTwinStore({ machineOrder: STREAM_MACHINE_ORDER, bufferOrder: BUFFER_IDS }),
  );
  const ingestedStep = useRef(-1);

  // Auto-seed (?seed=, default 777) so panels/topology render without a
  // click; further episodes come from ControlsBar via onEpisode. A deep
  // ?episode= link streams that episode directly (T13 storm driver).
  // A failed seed surfaces the error state with a retry (not silent).
  function seedNow(): void {
    setSeedError(false);
    postEpisode("", initialSeed(), [], true)
      .then((created) => setEpisodeId(created.episode_id))
      .catch(() => setSeedError(true));
  }

  useEffect(() => {
    if (initialEpisode() !== null) return;
    let cancelled = false;
    setSeedError(false);
    postEpisode("", initialSeed(), [], true)
      .then((created) => {
        if (!cancelled) setEpisodeId(created.episode_id);
      })
      .catch(() => {
        if (!cancelled) setSeedError(true);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    ingestedStep.current = -1;
    chartStore.reset();
  }, [source.episodeId, chartStore]);

  useEffect(() => {
    const p = source.panelTick;
    if (p === null || p.step <= ingestedStep.current) return;
    ingestedStep.current = p.step;
    const row: Tick = {
      step: p.step,
      states: p.states,
      obs: p.obs,
      throughput: p.throughput,
      buffers: p.buffers,
      sbuf_level: p.sbuf_level,
      events_at_k: [],
      faults: [],
      quality: p.quality,
    };
    chartStore.ingest(row);
  }, [source.panelTick, chartStore]);

  // Faceplate rail owns selection + the selected-machine sparkline via the
  // shared chartStore (single StripChart mount — no duplicate strip-* ids).
  // Fault specs for the topology overlay, parsed from the buffered row at
  // the shared cursor (materialized tick shape via toFaultSpec).
  const faults: readonly FaultSpec[] = useMemo(() => {
    const raw = source.rowJson(source.cursor);
    if (raw === undefined) return [];
    try {
      const body: unknown = JSON.parse(raw);
      if (typeof body !== "object" || body === null || !("faults" in body)) return [];
      const list = (body as { readonly faults?: unknown }).faults;
      if (!Array.isArray(list)) return [];
      return list
        .filter((f): f is Record<string, unknown> => typeof f === "object" && f !== null && !Array.isArray(f))
        .map((f) => {
          try {
            return toFaultSpec(f);
          } catch {
            return null;
          }
        })
        .filter((f): f is FaultSpec => f !== null);
    } catch {
      return [];
    }
  }, [source, source.cursor]);

  const showSeedError = episodeId === null && seedError;
  const showSkeleton = episodeId === null && !seedError;

  return (
    <div className="sim-shell" data-testid="sim-shell">
      <header className="sim-shell__header sim-box">
        <h1 className="px-h2">Verdandi Twin — /sim</h1>
        {/* L1 strip: tick KPIs + c7tail_final ride panelTick; episode
            sbuf/flow finals are not plumbed through TickSource (playback is
            read-only), so the header passes null and those fields show "—". */}
        <LineHeader
          tick={source.panelTick}
          episodeHeader={null}
          episodeId={source.episodeId}
          speed={source.speed}
          playing={source.playing}
          selectedId={selectedId}
          store={chartStore}
        />
      </header>
      <div className="sim-shell__body">
        {showSeedError && (
          <section data-testid="sim-seed-error" role="alert" className="sim-box sim-shell__full">
            <h2 className="px-h2">No episode</h2>
            <p data-testid="sim-seed-error-text">
              Could not start an episode — the bridge is unreachable.
            </p>
            <button type="button" data-testid="sim-retry" onClick={seedNow}>
              Retry
            </button>
          </section>
        )}
        {showSkeleton && <SimSkeleton />}
        {!showSkeleton && (
          <>
            <section className="sim-shell__canvas sim-box" data-testid="sim-canvas" aria-label="topology canvas">
              <TopologyView
                tick={source.tick}
                connected={source.connected}
                faults={faults}
                onRetry={source.reconnect}
                selectedId={selectedId}
                onSelect={setSelectedId}
                panelTick={source.panelTick}
              />
            </section>
            <aside className="sim-shell__rail" data-testid="sim-rail" aria-label="detail rail">
              <MachinePanel
                tick={source.panelTick}
                selectedId={selectedId}
                onSelect={setSelectedId}
                store={chartStore}
                faults={faults}
                onStepTo={source.stepTo}
              />
            </aside>
          </>
        )}
      </div>
      <footer className="sim-shell__dock sim-box" data-testid="sim-dock" aria-label="control dock">
        <ControlsBar external={{ source, onEpisode: setEpisodeId }} />
        <BufferBars tick={source.panelTick} />
        <EventFeed events={source.events} />
        <Legends />
      </footer>
    </div>
  );
}
