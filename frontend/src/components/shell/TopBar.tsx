import { useState } from "react";
import { useLocation } from "react-router-dom";
import { useTwinStream } from "../../sim/TwinStreamProvider";
import { SPEEDS, T_TOTAL } from "../controls/types";
import "./shell.css";

export function TopBar(): React.JSX.Element {
  const location = useLocation();
  const {
    source,
    episodeId,
    scenarioOpen,
    setScenarioOpen,
    guideOpen,
    setGuideOpen,
    hasVisitedGuide,
    markGuideVisited,
    stepPrevEvent,
    stepNextEvent,
    faults,
  } = useTwinStream();

  const [copied, setCopied] = useState(false);

  // Derive current page title from pathname
  const pageTitle =
    location.pathname === "/anomalies"
      ? "Anomaly Detection"
      : location.pathname === "/metrics"
        ? "Plant Metrics"
        : "Live View";

  const cursor = Math.max(0, source.cursor);
  const playing = source.playing;
  const speed = source.speed;

  const handleCopyEpisode = () => {
    if (!episodeId) return;
    navigator.clipboard?.writeText(episodeId);
    setCopied(true);
    setTimeout(() => setCopied(false), 1800);
  };

  const handleOpenGuide = () => {
    markGuideVisited();
    setGuideOpen(!guideOpen);
  };

  const shortEpisode = episodeId ? `${episodeId.slice(0, 8)}…` : "connecting…";

  // Calculate fault windows for timeline markers
  const faultRanges = faults.map((f) => ({
    id: f.id,
    startPercent: Math.min(100, Math.max(0, (f.t0 / T_TOTAL) * 100)),
    widthPercent: Math.min(100, Math.max(1, (f.dur / T_TOTAL) * 100)),
  }));

  return (
    <header
      className="vd-top-bar"
      data-testid="top-bar"
      aria-label="top transport bar"
    >
      <div className="vd-top-brand">
        <span className="vd-top-logo">VERDANDI</span>
        <span className="vd-top-divider">/</span>
        <h1 className="vd-top-page-title">{pageTitle}</h1>
      </div>

      <div className="vd-top-status">
        <div
          className={`vd-status-chip ${source.connected ? "is-live" : "is-offline"}`}
          data-testid="status-chip"
          title={`Simulation status: ${source.connected ? "Connected" : "Disconnected"}`}
        >
          <span className="vd-status-dot" aria-hidden="true" />
          <span className="vd-status-text">
            {source.connected ? "LIVE" : "DISCONNECTED"}
          </span>
          <span className="vd-status-step">
            step {cursor}/{T_TOTAL}
          </span>
        </div>

        <button
          type="button"
          className="vd-episode-chip"
          data-testid="episode-chip"
          onClick={handleCopyEpisode}
          title="Click to copy full Episode ID"
        >
          <span className="vd-ep-label">EP</span>
          <span className="vd-ep-value">{copied ? "COPIED!" : shortEpisode}</span>
        </button>
      </div>

      {/* Primary SCADA Transport Console */}
      <div
        className="vd-transport-bar"
        data-testid="transport-bar"
        role="region"
        aria-label="simulation transport controls"
      >
        <div className="vd-transport-buttons">
          <button
            type="button"
            className="vd-ctrl-btn"
            data-testid="topbar-step-prev-event"
            onClick={stepPrevEvent}
            title="Jump to previous event"
            aria-label="Jump to previous event"
          >
            |◄
          </button>
          <button
            type="button"
            className="vd-ctrl-btn"
            data-testid="topbar-step-back"
            onClick={() => {
              source.setPlaying(false);
              source.stepTo(Math.max(0, cursor - 1));
            }}
            title="Step backward one tick (-1)"
            aria-label="Step backward"
          >
            ◄
          </button>
          <button
            type="button"
            className={`vd-ctrl-btn vd-play-pause-btn ${playing ? "is-playing" : "is-paused"}`}
            data-testid="topbar-play-pause"
            onClick={() => {
              if (!playing && cursor >= T_TOTAL - 1) {
                source.stepTo(0);
                source.setPlaying(true);
              } else {
                source.setPlaying(!playing);
              }
            }}
            title={playing ? "Pause simulation" : "Play simulation"}
            aria-label={playing ? "Pause" : "Play"}
          >
            {playing ? "❚❚" : "►"}
          </button>
          <button
            type="button"
            className="vd-ctrl-btn"
            data-testid="topbar-step-fwd"
            onClick={() => {
              source.setPlaying(false);
              source.stepTo(Math.min(T_TOTAL - 1, cursor + 1));
            }}
            title="Step forward one tick (+1)"
            aria-label="Step forward"
          >
            ►
          </button>
          <button
            type="button"
            className="vd-ctrl-btn"
            data-testid="topbar-step-next-event"
            onClick={stepNextEvent}
            title="Jump to next event"
            aria-label="Jump to next event"
          >
            ►|
          </button>
        </div>

        {/* Scrubber slider with fault window indicators */}
        <div className="vd-scrubber-container">
          <div className="vd-scrubber-track-wrap">
            <input
              type="range"
              min={0}
              max={T_TOTAL - 1}
              value={cursor}
              onChange={(e) => {
                source.setPlaying(false);
                source.stepTo(Number(e.target.value));
              }}
              className="vd-scrubber-slider"
              data-testid="topbar-scrubber"
              aria-label="simulation step scrubber"
            />
            {faultRanges.map((fr) => (
              <span
                key={fr.id}
                className="vd-scrubber-fault-tick"
                style={{
                  left: `${fr.startPercent}%`,
                  width: `${fr.widthPercent}%`,
                }}
                title={`Fault window: ${fr.id}`}
              />
            ))}
          </div>
        </div>

        {/* Speed Segmented Control */}
        <div
          className="vd-speed-control"
          role="radiogroup"
          aria-label="simulation speed"
          data-testid="speed-control"
        >
          {SPEEDS.map((s) => (
            <button
              key={s}
              type="button"
              className={`vd-speed-btn ${speed === s ? "is-active" : ""}`}
              onClick={() => source.setSpeed(s)}
              aria-checked={speed === s}
              role="radio"
              data-testid={`speed-${s}x`}
              title={`${s}x speed (${s * 4} steps/sec)`}
            >
              {s}x
            </button>
          ))}
        </div>
      </div>

      <div className="vd-top-actions">
        <button
          type="button"
          className={`vd-action-btn ${scenarioOpen ? "is-active" : ""}`}
          data-testid="btn-scenario"
          onClick={() => setScenarioOpen(!scenarioOpen)}
          aria-expanded={scenarioOpen}
        >
          ⚙ Scenario
        </button>

        <button
          type="button"
          className={`vd-action-btn vd-guide-btn ${guideOpen ? "is-active" : ""}`}
          data-testid="btn-guide"
          onClick={handleOpenGuide}
          aria-expanded={guideOpen}
        >
          <span>? How it works</span>
          {!hasVisitedGuide && (
            <span
              className="vd-btn-pulse-dot"
              aria-label="new guide notice"
            />
          )}
        </button>
      </div>
    </header>
  );
}
