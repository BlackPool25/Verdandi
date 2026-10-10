import { ControlsBar } from "../components/controls/ControlsBar";
import { EventFeed } from "../components/events/EventFeed";
import {
  BufferBars,
  Legends,
  MachinePanel,
} from "../components/panels";
import { LineHeader } from "./LineHeader";
import { TopologyView } from "../topology/TopologyView";
import { useTwinStream } from "./TwinStreamProvider";
import "./simShell.css";

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
  const {
    source,
    store: chartStore,
    selectedId,
    setSelectedId,
    faults,
    showSkeleton,
    seedNow,
    seedError,
    episodeId,
    setEpisodeId,
  } = useTwinStream();

  const showSeedError = episodeId === null && seedError;

  return (
    <div className="sim-shell" data-testid="sim-shell">
      <header className="sim-shell__header sim-box">
        <h1 className="px-h2">Verdandi Twin — /sim</h1>
        <LineHeader
          tick={source.panelTick}
          episodeHeader={source.episodeHeader}
          episodeId={source.episodeId}
          energy={source.energy}
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
