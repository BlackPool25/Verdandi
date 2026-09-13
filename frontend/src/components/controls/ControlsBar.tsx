import { useEffect, useMemo, useRef, useState } from "react";
import { EpisodeError, bridgeBase, openTickStream, postEpisode } from "./api";
import { FaultForm } from "./FaultForm";
import { intervalMs, stepBy } from "./playback";
import {
  SPEEDS,
  STEPS_PER_SEC_AT_1X,
  T_TOTAL,
  VALIDATION_HINTS,
  type EpisodeCreated,
  type FaultDraft,
  type TickRow,
} from "./types";
import { clientWarnings } from "./validate";
import type { TickSource } from "../../sim/tickSource";

// External shared-source mode (used on /sim): episode creation feeds the
// shared tickSource, and playback reads/writes its cursor — panels,
// topology and controls render one episode from one EventSource.
// Standalone mode (no `external`, e.g. /controls.html harness) keeps the
// internal stream untouched.
export interface ControlsExternal {
  readonly source: TickSource;
  readonly onEpisode: (id: string) => void;
}

function parseRow(raw: string | undefined): TickRow | null {
  if (raw === undefined) return null;
  try {
    return JSON.parse(raw) as TickRow;
  } catch {
    return null;
  }
}

export function ControlsBar(props: { readonly external?: ControlsExternal }): React.JSX.Element {
  const ext = props.external ?? null;
  const [base] = useState<string>(() => bridgeBase());
  const [seedText, setSeedText] = useState<string>("777");
  const [faults, setFaults] = useState<FaultDraft[]>([]);
  const [natural, setNatural] = useState<boolean>(true);
  const [episode, setEpisode] = useState<EpisodeCreated | null>(null);
  const [formError, setFormError] = useState<string>("");
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [playingLocal, setPlayingLocal] = useState<boolean>(false);
  const [speedLocal, setSpeedLocal] = useState<number>(1);
  const [cursorLocal, setCursorLocal] = useState<number>(0);
  const [rowCountLocal, setRowCountLocal] = useState<number>(0);

  const rowsRef = useRef<TickRow[]>([]);
  const closeStreamRef = useRef<(() => void) | null>(null);
  const cursorRef = useRef<number>(0);

  // Playback state: shared source on /sim, local state on the harness.
  const playing = ext !== null ? ext.source.playing : playingLocal;
  const speed = ext !== null ? ext.source.speed : speedLocal;
  const cursor = ext !== null ? Math.max(0, ext.source.cursor) : cursorLocal;
  const rowCount = ext !== null ? ext.source.rowCount : rowCountLocal;
  cursorRef.current = cursor;

  // Control availability + identity follow the shared episode on /sim
  // (deep ?episode= links never populate the internal New-episode state).
  const sharedEpisodeId = ext?.source.episodeId ?? null;
  const canControl = ext !== null ? sharedEpisodeId !== null : episode !== null;

  function setPlaying(p: boolean | ((prev: boolean) => boolean)): void {
    if (ext !== null) {
      ext.source.setPlaying(typeof p === "function" ? p(ext.source.playing) : p);
      return;
    }
    setPlayingLocal(p);
  }

  function setSpeed(s: number): void {
    if (ext !== null) {
      ext.source.setSpeed(s);
      return;
    }
    setSpeedLocal(s);
  }

  function setCursor(v: number | ((prev: number) => number)): void {
    const next = typeof v === "function" ? v(cursor) : v;
    if (ext !== null) {
      ext.source.stepTo(next);
      return;
    }
    setCursorLocal(next);
  }

  useEffect(() => {
    if (!playing || episode === null) return;
    if (ext !== null) return;
    const id = window.setInterval(() => {
      const n = rowsRef.current.length;
      if (n === 0) return;
      if (cursorRef.current + 1 >= n) {
        setPlayingLocal(false);
        return;
      }
      setCursorLocal((c) => (c + 1 < n ? c + 1 : c));
    }, intervalMs(speed));
    return () => window.clearInterval(id);
  }, [playing, speed, episode, ext]);

  useEffect(() => {
    return () => {
      closeStreamRef.current?.();
      closeStreamRef.current = null;
    };
  }, []);

  async function startEpisode(): Promise<void> {
    const warnings = clientWarnings(seedText, faults);
    if (warnings.length > 0) {
      setFormError(warnings.join(" | "));
    }
    setSubmitting(true);
    try {
      const seed = Number(seedText);
      closeStreamRef.current?.();
      closeStreamRef.current = null;
      rowsRef.current = [];
      setRowCountLocal(0);
      setCursorLocal(0);
      const created = await postEpisode(base, seed, faults, natural);
      setEpisode(created);
      setFormError("");
      if (ext !== null) {
        ext.onEpisode(created.episode_id);
        ext.source.setPlaying(true);
        return;
      }
      const close = openTickStream(base, created.episode_id, (row) => {
        rowsRef.current[row.step] = row;
        setRowCountLocal(rowsRef.current.filter((r) => r !== undefined).length);
      });
      closeStreamRef.current = close;
      setPlayingLocal(true);
    } catch (e) {
      if (e instanceof EpisodeError) {
        setFormError(e.detail);
      } else {
        setFormError(e instanceof Error ? e.message : "episode request failed");
      }
    } finally {
      setSubmitting(false);
    }
  }

  // T6 render throttle: tick-json parse+stringify memoized on the raw row
  // (ext mode) or cursor/rowCount (local mode). Unrelated re-renders (seed
  // typing, fault form, play/pause) no longer pay a full-tick stringify.
  const isExt = ext !== null;
  const rawTick = isExt && ext !== null ? ext.source.rowJson(cursor) : undefined;
  const current: TickRow | null = useMemo(() => {
    if (isExt) return parseRow(rawTick);
    return rowsRef.current[cursor] ?? null;
    // rowsRef is read under the cursor/rowCountLocal deps by design.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isExt, rawTick, cursor, rowCountLocal]);
  const tickJson = useMemo(
    () => (current === null ? "null" : JSON.stringify(current)),
    [current],
  );

  return (
    <div className="controls-toolbar">
      <section aria-label="sim controls">
        <div className="controls-toolbar__row">
          <button type="button" data-testid="play-pause" disabled={!canControl} onClick={() => setPlaying((p) => !p)}>
            {playing ? "Pause" : "Play"}
          </button>
          <p data-testid="cursor">
            Step {cursor} / {T_TOTAL}
          </p>
        </div>
        <details data-testid="details-episode" open>
          <summary>Episode setup</summary>
          <label>
            seed
            <input data-testid="seed-input" inputMode="numeric" value={seedText} onChange={(e) => setSeedText(e.target.value)} />
          </label>
          <button type="button" data-testid="new-episode" disabled={submitting} onClick={() => void startEpisode()}>
            {submitting ? "Starting…" : "Start new episode"}
          </button>
          <label>
            <input
              data-testid="natural-toggle"
              type="checkbox"
              checked={natural}
              onChange={(e) => setNatural(e.target.checked)}
            />
            enable_natural_breakdown
          </label>
          <p>
            episode <span data-testid="episode-id">{episode === null ? (sharedEpisodeId ?? "none") : episode.episode_id}</span>
          </p>
          <p>
            digest <span data-testid="episode-digest">{episode === null ? "none" : episode.replay_digest}</span>
          </p>
          <p data-testid="validation-hints">{VALIDATION_HINTS}</p>
          <p data-testid="form-error">{formError}</p>
          {episode !== null && episode.noop_warning && (
            <p data-testid="noop-warning">noop_warning: quality fault outside ASM2 has no effect (accepted, silent no-op)</p>
          )}
        </details>
        <details data-testid="details-playback" open>
          <summary>Playback</summary>
          <label>
            speed (1x={STEPS_PER_SEC_AT_1X} steps/s)
            <select data-testid="speed-select" value={String(speed)} onChange={(e) => setSpeed(Number(e.target.value))}>
              {SPEEDS.map((s) => (
                <option key={s} value={String(s)}>
                  {s}x
                </option>
              ))}
            </select>
          </label>
          <button
            type="button"
            data-testid="step-back"
            disabled={!canControl}
            onClick={() => {
              setPlaying(false);
              setCursor((c) => stepBy(c, -1));
            }}
          >
            Step −1
          </button>
          <button
            type="button"
            data-testid="step-fwd"
            disabled={!canControl}
            onClick={() => {
              setPlaying(false);
              setCursor((c) => (c + 1 < rowsRef.current.length || ext !== null ? stepBy(c, 1) : c));
            }}
          >
            Step +1
          </button>
          <p>
            rows <span data-testid="row-count">{rowCount}</span>
          </p>
        </details>
        <details data-testid="details-faults" open>
          <summary>Faults</summary>
          <FaultForm faults={faults} onAdd={(f) => setFaults((prev) => [...prev, f])} onRemove={(id) => setFaults((prev) => prev.filter((f) => f.id !== id))} />
          <pre data-testid="episode-faults" style={{ whiteSpace: "pre-wrap", wordBreak: "break-word" }}>{episode === null ? "[]" : JSON.stringify(episode.faults)}</pre>
        </details>
        <details data-testid="details-tick">
          <summary>Tick JSON</summary>
          <pre data-testid="tick-json" style={{ whiteSpace: "pre-wrap", wordBreak: "break-word" }}>{tickJson}</pre>
        </details>
      </section>
    </div>
  );
}
