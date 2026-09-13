// L1 header strip: honest per-tick line KPIs + episode finals, nothing else.
// Values derive verbatim from selectors lineStatsFor/episodeStatsFor — no
// rates, no availability math. Missing tick or missing keys render "—",
// never a fabricated zero. Badge throttle: subscribes via useBadges and
// flushes the store on a 100ms interval (same gate StripChart subscribes to).
import { useEffect } from "react";
import { useBadges } from "../components/charts/useBadges";
import {
  episodeStatsFor,
  lineStatsFor,
  type EpisodeHeader,
  type PanelTick,
} from "../components/panels/selectors";
import type { TwinStore } from "../store/twinStore";

export interface LineHeaderProps {
  readonly tick: PanelTick | null;
  readonly episodeHeader: EpisodeHeader | null | undefined;
  readonly episodeId: string | null;
  readonly speed: number;
  readonly playing: boolean;
  readonly selectedId: string | null;
  readonly store: TwinStore;
}

const MISSING = "—";

function fmt(v: number | null): string {
  return v === null ? MISSING : String(v);
}

const ROW: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: 16,
  overflow: "hidden",
  whiteSpace: "nowrap",
  fontSize: 16,
};

export function LineHeader(props: LineHeaderProps): React.JSX.Element {
  const { tick, episodeHeader, episodeId, speed, playing, selectedId, store } = props;
  const badges = useBadges(store);
  useEffect(() => {
    const id = window.setInterval(() => store.flushBadges(), 100);
    return () => window.clearInterval(id);
  }, [store]);
  const line = tick === null ? null : lineStatsFor(tick);
  const ep = episodeStatsFor(episodeHeader);
  // c7tail_final arrives on the header event (controller) and rides the tick;
  // prefer the episode selector, fall back to the tick payload, else "—".
  const c7 = ep.c7tailFinal ?? tick?.c7tailFinal ?? null;
  const step = tick?.step ?? (badges.cursor >= 0 ? badges.cursor : null);
  return (
    <div data-testid="line-header" aria-label="line header" style={ROW} className="px-line-header">
      <span data-testid="line-header-crumb" className="px-hdr-badge px-hdr-crumb">Line › {selectedId ?? MISSING}</span>
      <span data-testid="line-header-episode" className="px-hdr-badge">ep {episodeId ?? MISSING}</span>
      <span data-testid="line-header-step" className="px-hdr-badge px-hdr-step">step {step ?? MISSING}</span>
      <span data-testid="line-header-speed" className="px-hdr-badge">{speed}x</span>
      <span data-testid="line-header-playing" className="px-hdr-badge">{playing ? "playing" : "paused"}</span>
      {tick === null && <span data-testid="line-header-empty" className="px-hdr-badge">no tick yet</span>}
      <span data-testid="line-header-tput" className="px-hdr-badge">tput {line === null ? MISSING : line.tputSum}</span>
      <span data-testid="line-header-run" className="px-hdr-badge px-hdr-run">RUN {line === null ? MISSING : line.run}</span>
      <span data-testid="line-header-blocked" className="px-hdr-badge px-hdr-blocked">BLOCKED {line === null ? MISSING : line.blocked}</span>
      <span data-testid="line-header-starved" className="px-hdr-badge px-hdr-starved">STARVED {line === null ? MISSING : line.starved}</span>
      <span data-testid="line-header-down" className="px-hdr-badge px-hdr-down">DOWN {line === null ? MISSING : line.down}</span>
      <span data-testid="line-header-sbuf" className="px-hdr-badge">SBUF {line === null ? MISSING : line.sbufLevel}</span>
      {line !== null && line.sbufHigh && <span data-testid="line-header-sbuf-high" className="px-hdr-badge px-hdr-warn">HIGH</span>}
      <span data-testid="line-header-sunk" className="px-hdr-badge">sunk {fmt(ep.sunk)}</span>
      <span data-testid="line-header-scrapped" className="px-hdr-badge">scrapped {fmt(ep.scrapped)}</span>
      <span data-testid="line-header-reworked" className="px-hdr-badge">reworked {fmt(ep.reworked)}</span>
      <span data-testid="line-header-c7tail" className="px-hdr-badge">c7tail_final {fmt(c7)}</span>
    </div>
  );
}
