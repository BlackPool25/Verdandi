import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { useLocation } from "react-router-dom";
import { postEpisode } from "../components/controls/api";
import { toFaultSpec } from "../components/events/anomaly";
import type { FaultSpec } from "../components/events/types";
import { BUFFER_IDS, type Tick } from "../store/tick";
import { createTwinStore, type TwinStore } from "../store/twinStore";
import {
  STREAM_MACHINE_ORDER,
  useTickSource,
  type TickSource,
} from "./tickSource";
import type { EpisodeCreated, FaultDraft } from "../components/controls/types";

export interface TwinStreamContextValue {
  readonly episodeId: string | null;
  readonly setEpisodeId: (id: string | null) => void;
  readonly source: TickSource;
  readonly store: TwinStore;
  readonly selectedId: string | null;
  readonly setSelectedId: (id: string | null) => void;
  readonly faults: readonly FaultSpec[];
  readonly seedNow: () => void;
  readonly seedError: boolean;
  readonly showSkeleton: boolean;
  readonly guideOpen: boolean;
  readonly setGuideOpen: (open: boolean) => void;
  readonly scenarioOpen: boolean;
  readonly setScenarioOpen: (open: boolean) => void;
  readonly hasVisitedGuide: boolean;
  readonly markGuideVisited: () => void;
  readonly startNewEpisode: (
    seed: number,
    faults: FaultDraft[],
    natural: boolean,
  ) => Promise<EpisodeCreated>;
  readonly jumpToStep: (step: number) => void;
  readonly stepPrevEvent: () => void;
  readonly stepNextEvent: () => void;
}

const TwinStreamContext = createContext<TwinStreamContextValue | null>(null);

export function useTwinStream(): TwinStreamContextValue {
  const ctx = useContext(TwinStreamContext);
  if (ctx === null) {
    throw new Error("useTwinStream must be used within a TwinStreamProvider");
  }
  return ctx;
}

export function TwinStreamProvider({
  children,
}: {
  readonly children: ReactNode;
}): React.JSX.Element {
  const location = useLocation();
  const searchParams = useMemo(
    () => new URLSearchParams(location.search),
    [location.search],
  );
  const epParam = searchParams.get("episode");
  const probeParam = searchParams.get("probe");
  const seedParam = searchParams.get("seed");

  const [episodeId, setEpisodeId] = useState<string | null>(() => epParam);
  const [seedError, setSeedError] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(
    () => probeParam,
  );
  const [guideOpen, setGuideOpen] = useState(
    () => searchParams.get("guide") !== null,
  );
  const [scenarioOpen, setScenarioOpen] = useState(false);
  const [hasVisitedGuide, setHasVisitedGuide] = useState(() => {
    try {
      return localStorage.getItem("verdandi_guide_visited") === "true";
    } catch {
      return false;
    }
  });

  const markGuideVisited = useCallback(() => {
    setHasVisitedGuide(true);
    try {
      localStorage.setItem("verdandi_guide_visited", "true");
    } catch {
      // ignore
    }
  }, []);

  const [chartStore] = useState(() =>
    createTwinStore({
      machineOrder: STREAM_MACHINE_ORDER,
      bufferOrder: BUFFER_IDS,
    }),
  );

  // Periodic badge flushing so StripChart captions and status stay live
  useEffect(() => {
    const id = window.setInterval(() => {
      chartStore.flushBadges();
    }, 100);
    return () => window.clearInterval(id);
  }, [chartStore]);

  const source = useTickSource({ episodeId });
  const ingestedStep = useRef(-1);

  // Sync with URL query parameters on navigation
  useEffect(() => {
    if (epParam && epParam !== episodeId) {
      setEpisodeId(epParam);
    }
  }, [epParam, episodeId]);

  useEffect(() => {
    if (probeParam && probeParam !== selectedId) {
      setSelectedId(probeParam);
    }
  }, [probeParam, selectedId]);

  const targetSeed = useMemo(() => {
    const raw = Number(seedParam ?? "777");
    return Number.isInteger(raw) && raw >= 0 ? raw : 777;
  }, [seedParam]);

  const seedNow = useCallback(() => {
    setSeedError(false);
    postEpisode("", targetSeed, [], true)
      .then((created) => setEpisodeId(created.episode_id))
      .catch(() => setSeedError(true));
  }, [targetSeed]);

  // Initial episode creation if no episode parameter
  useEffect(() => {
    if (epParam !== null) return;
    let cancelled = false;
    setSeedError(false);
    postEpisode("", targetSeed, [], true)
      .then((created) => {
        if (!cancelled) setEpisodeId(created.episode_id);
      })
      .catch(() => {
        if (!cancelled) setSeedError(true);
      });
    return () => {
      cancelled = true;
    };
  }, [epParam, targetSeed]);

  // Reset store whenever episode changes
  useEffect(() => {
    ingestedStep.current = -1;
    chartStore.reset();
  }, [source.episodeId, chartStore]);

  // Ingest ticks into cyclic ring buffers
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
      events_at_k: [...p.events_at_k],
      faults: p.faults.map((f) => ({ ...f })),
      quality: p.quality,
      currents: p.currents,
    };
    chartStore.ingest(row);
  }, [source.panelTick, chartStore]);

  // Parse faults at the active cursor
  const faults: readonly FaultSpec[] = useMemo(() => {
    const raw = source.rowJson(source.cursor);
    if (raw === undefined) return [];
    try {
      const body: unknown = JSON.parse(raw);
      if (typeof body !== "object" || body === null || !("faults" in body))
        return [];
      const list = (body as { readonly faults?: unknown }).faults;
      if (!Array.isArray(list)) return [];
      return list
        .filter(
          (f): f is Record<string, unknown> =>
            typeof f === "object" && f !== null && !Array.isArray(f),
        )
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
  }, [source]);

  const startNewEpisode = useCallback(
    async (
      seed: number,
      faultDrafts: FaultDraft[],
      natural: boolean,
    ): Promise<EpisodeCreated> => {
      const created = await postEpisode("", seed, faultDrafts, natural);
      setEpisodeId(created.episode_id);
      source.setPlaying(true);
      return created;
    },
    [source],
  );

  const jumpToStep = useCallback(
    (step: number) => {
      source.stepTo(step);
    },
    [source],
  );

  const stepPrevEvent = useCallback(() => {
    const currentStep = source.cursor;
    const events = source.events;
    let target = -1;
    for (let i = events.length - 1; i >= 0; i--) {
      const ev = events[i];
      if (ev !== undefined && ev.t < currentStep) {
        target = ev.t;
        break;
      }
    }
    if (target >= 0) {
      source.stepTo(target);
    } else if (currentStep > 0) {
      source.stepTo(0);
    }
  }, [source]);

  const stepNextEvent = useCallback(() => {
    const currentStep = source.cursor;
    const events = source.events;
    let target = -1;
    for (let i = 0; i < events.length; i++) {
      const ev = events[i];
      if (ev !== undefined && ev.t > currentStep) {
        target = ev.t;
        break;
      }
    }
    if (target >= 0) {
      source.stepTo(target);
    }
  }, [source]);

  const showSkeleton = episodeId === null && !seedError;

  const value = useMemo<TwinStreamContextValue>(
    () => ({
      episodeId,
      setEpisodeId,
      source,
      store: chartStore,
      selectedId,
      setSelectedId,
      faults,
      seedNow,
      seedError,
      showSkeleton,
      guideOpen,
      setGuideOpen,
      scenarioOpen,
      setScenarioOpen,
      hasVisitedGuide,
      markGuideVisited,
      startNewEpisode,
      jumpToStep,
      stepPrevEvent,
      stepNextEvent,
    }),
    [
      episodeId,
      source,
      chartStore,
      selectedId,
      faults,
      seedNow,
      seedError,
      showSkeleton,
      guideOpen,
      scenarioOpen,
      hasVisitedGuide,
      markGuideVisited,
      startNewEpisode,
      jumpToStep,
      stepPrevEvent,
      stepNextEvent,
    ],
  );

  return (
    <TwinStreamContext.Provider value={value}>
      {children}
    </TwinStreamContext.Provider>
  );
}
