import { useEffect, useRef, useState } from "react";
import type { TickPatch } from "../topology/TopologyView";
import type { TwinEvent } from "../components/events/types";
import { BUFFER_IDS, parseTick } from "../store/tick";
import { intervalMs } from "../components/controls/playback";
import type { PanelTick } from "../components/panels/selectors";
import {
  STREAM_MACHINE_ORDER,
  T_TOTAL,
  parseFeedEvents,
  parseLiveTick,
  toPatch,
  type StreamHandle,
} from "./streamCodec";
import { TickStreamController } from "./streamController";

// T10 stream lifecycle: single EventSource, ?from_step=k resume, cursor-only
// speed, episode switch closes the old stream, byte budget, 300/300 ticks.
// Backend (T2) is read-only: header + 300 tick frames, from_step is cursor-only.
// Codec (streamCodec) + controller (streamController) live in sibling
// modules; this file owns the shared playback hook. Codec/controller names
// re-export here so existing importers keep working.
export {
  BYTE_BUDGET,
  STREAM_MACHINE_ORDER,
  T_TOTAL,
  parseFeedEvents,
  parseLiveTick,
  streamUrl,
  toPatch,
} from "./streamCodec";
export { TickStreamController } from "./streamController";
export type {
  LiveTick,
  OpenStream,
  StreamHandle,
} from "./streamCodec";
export type { ControllerOptions } from "./streamController";

// Panels consume the same buffered rows as the topology cursor: parse one
// raw row into the frozen-schema PanelTick (single EventSource, single
// episode — replaces the deleted panelFeed hook). Null on unparseable rows.
export function toPanelTick(raw: string, c7tailFinal: number | null): PanelTick | null {
  let data: unknown = null;
  try {
    data = JSON.parse(raw) as unknown;
  } catch {
    return null;
  }
  let tick;
  try {
    tick = parseTick(data);
  } catch {
    return null;
  }
  return {
    step: tick.step,
    states: tick.states,
    obs: tick.obs,
    throughput: tick.throughput,
    buffers: tick.buffers,
    sbuf_level: tick.sbuf_level,
    quality: tick.quality,
    machineOrder: STREAM_MACHINE_ORDER,
    bufferOrder: BUFFER_IDS,
    c7tailFinal,
  };
}

export interface TickSource {
  readonly tick: TickPatch | null;
  readonly panelTick: PanelTick | null;
  readonly events: readonly TwinEvent[];
  readonly connected: boolean;
  readonly cursor: number;
  readonly rowCount: number;
  readonly playing: boolean;
  readonly totalBytes: number;
  readonly complete: boolean;
  readonly reconnecting: boolean;
  readonly episodeId: string | null;
  readonly speed: number;
  readonly setSpeed: (s: number) => void;
  readonly setPlaying: (p: boolean) => void;
  readonly stepTo: (step: number) => boolean;
  readonly rowJson: (step: number) => string | undefined;
  readonly startEpisode: (id: string) => void;
  readonly disconnect: () => void;
  readonly reconnect: () => void;
}

export interface TickSourceOptions {
  readonly episodeId?: string | null;
  readonly speed?: number;
  readonly base?: string;
}

function defaultOpen(url: string): StreamHandle {
  return new EventSource(url) as unknown as StreamHandle;
}

export function useTickSource(opts: TickSourceOptions = {}): TickSource {
  const base = opts.base ?? "";
  const [ctrl] = useState(() => new TickStreamController(defaultOpen));
  const [, bump] = useState(0);
  const [tick, setTick] = useState<TickPatch | null>(null);
  const [panelTick, setPanelTick] = useState<PanelTick | null>(null);
  const [feedEvents, setFeedEvents] = useState<readonly TwinEvent[]>([]);
  const feedCovered = useRef(-1);
  const [probeOk, setProbeOk] = useState(false);
  const [playing, setPlaying] = useState(true);
  const [played, setPlayed] = useState(-1);
  const playedRef = useRef(-1);
  const episodeOpt = opts.episodeId ?? null;
  const speedOpt = opts.speed ?? 1;

  useEffect(() => ctrl.subscribe(() => bump((n) => n + 1)), [ctrl]);

  // Bridge probe: same-origin /schema must parse as the bridge schema
  // document (vite SPA fallback serves index.html with 200 — content check).
  useEffect(() => {
    let cancelled = false;
    fetch("/schema", { headers: { accept: "application/json" } })
      .then((r) => r.json())
      .then((j: unknown) => {
        if (cancelled) return;
        const keys =
          typeof j === "object" && j !== null && "tick_keys" in j
            ? (j as { readonly tick_keys?: unknown }).tick_keys
            : undefined;
        setProbeOk(Array.isArray(keys) && keys.includes("throughput"));
      })
      .catch(() => {
        if (!cancelled) setProbeOk(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // Episode wiring: a new episode_id closes the old stream (single-stream
  // invariant lives in the controller); unmount closes the stream.
  // A new episode resets the shared playback cursor and autoplays.
  useEffect(() => {
    if (episodeOpt === null) return;
    playedRef.current = -1;
    setPlayed(-1);
    setTick(null);
    setPanelTick(null);
    feedCovered.current = -1;
    setFeedEvents([]);
    setPlaying(true);
    ctrl.connect(episodeOpt, base);
    return () => ctrl.disconnect();
  }, [ctrl, episodeOpt, base]);

  useEffect(() => {
    ctrl.setSpeed(speedOpt);
  }, [ctrl, speedOpt]);

  // Shared playback cursor: topology patch + panel tick advance together
  // from the same buffered row, so panels/topology/controls never diverge.
  // Backpressure holds the cursor when the next row is not buffered yet.
  function rowsUpTo(next: number): TwinEvent[] {
    const out: TwinEvent[] = [];
    for (let k = 0; k <= next; k += 1) {
      const raw = ctrl.rowJson(k);
      if (raw === undefined) continue;
      try {
        out.push(...parseFeedEvents(JSON.parse(raw) as unknown));
      } catch {
        continue;
      }
    }
    return out;
  }

  function advanceTo(next: number): boolean {
    const raw = ctrl.rowJson(next);
    if (raw === undefined) return false;
    let data: unknown = null;
    try {
      data = JSON.parse(raw) as unknown;
    } catch {
      return false;
    }
    const row = parseLiveTick(data);
    if (row === null) return false;
    playedRef.current = next;
    setPlayed(next);
    setTick(toPatch(row));
    setPanelTick(toPanelTick(raw, ctrl.c7tailFinal()));
    if (next < feedCovered.current) {
      feedCovered.current = next;
      setFeedEvents(rowsUpTo(next));
    } else if (next > feedCovered.current) {
      feedCovered.current = next;
      setFeedEvents((prev) => [...prev, ...parseFeedEvents(data)]);
    }
    return true;
  }

  function stepTo(step: number): boolean {
    if (!Number.isInteger(step)) return false;
    return advanceTo(Math.min(T_TOTAL - 1, Math.max(0, step)));
  }

  // Playback at speed cadence over buffered rows; speed changes only reset
  // the interval — the cursor (played) is never recomputed.
  const cursor = ctrl.cursor();
  useEffect(() => {
    if (episodeOpt === null || cursor < 0 || !playing) return;
    const id = window.setInterval(() => {
      advanceTo(playedRef.current + 1);
    }, intervalMs(ctrl.speed()));
    return () => window.clearInterval(id);
    // advanceTo reads the controller + stable setters only.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ctrl, episodeOpt, cursor, playing]);

  // Stream health derives during render (not in an effect): the controller
  // emits on error with no new tick, the bump re-renders, and the banner
  // flips live. An effect keyed on [ctrl, episodeOpt, tick] would miss it.
  const connected =
    episodeOpt === null
      ? probeOk
      : !ctrl.reconnecting() && (ctrl.rowCount() > 0 || probeOk);

  return {
    tick,
    panelTick,
    events: feedEvents,
    connected,
    cursor: played,
    rowCount: ctrl.rowCount(),
    playing,
    totalBytes: ctrl.totalBytes(),
    complete: ctrl.complete(),
    reconnecting: ctrl.reconnecting(),
    episodeId: ctrl.episodeId(),
    speed: ctrl.speed(),
    setSpeed: (s: number) => ctrl.setSpeed(s),
    setPlaying,
    stepTo,
    rowJson: (step: number) => ctrl.rowJson(step),
    startEpisode: (id: string) => ctrl.connect(id, base),
    disconnect: () => ctrl.disconnect(),
    reconnect: () => ctrl.reconnect(),
  };
}
