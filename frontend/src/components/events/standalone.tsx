import { StrictMode, useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { ReactFlow, ReactFlowProvider } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { MachineNode } from "../../topology/MachineNode";
import { anomalyFor, toFaultSpec } from "./anomaly";
import { EventFeed } from "./EventFeed";
import { MachineEventFeed } from "./MachineEventFeed";
import type { FaultSpec, TwinEvent } from "./types";
import "./events.css";

// T9-owned dev harness (mirrors the T7 controls.html pattern): posts an
// episode, replays /stream ticks, and drives the feed + overlay preview.
// Production wiring (SimPage mount) belongs to T8/T10; this file is dev-only.
const ROSTER: readonly string[] = [
  ...Array.from({ length: 10 }, (_, i) => `A${i}`),
  ...Array.from({ length: 10 }, (_, i) => `B${i}`),
  ...Array.from({ length: 8 }, (_, i) => `C${i}`),
  "ASM0",
  "ASM1",
  "ASM2",
  "RWK0",
].sort();

const PROBE_MACHINES = ["B4", "B5", "B6", "B7"] as const;

interface TickRow {
  readonly step: number;
  readonly states: readonly string[];
  readonly events: readonly TwinEvent[];
}

const STYLE_PROBE: readonly TwinEvent[] = [
  { event: "DOWN", t: 150, machine: "B5", detail: {}, natural: false, gt_excluded: false, fault_id: "F-22" } as TwinEvent,
  { event: "DOWN", t: 40, machine: "A3", detail: {}, natural: true, gt_excluded: true, fault_id: null } as TwinEvent,
];

function stateMap(row: TickRow | null): Record<string, string> {
  const out: Record<string, string> = {};
  if (row === null) return out;
  ROSTER.forEach((id, i) => {
    const s = row.states[i];
    if (s !== undefined) out[id] = String(s);
  });
  return out;
}

function Harness(): React.JSX.Element {
  const [seed, setSeed] = useState("777");
  const [episodeId, setEpisodeId] = useState("none");
  const [faults, setFaults] = useState<readonly FaultSpec[]>([]);
  const [ticks, setTicks] = useState<readonly TickRow[]>([]);
  const [cursor, setCursor] = useState(0);
  const [machine, setMachine] = useState("B5");
  const [error, setError] = useState("");
  const sourceRef = useRef<EventSource | null>(null);

  useEffect(() => () => sourceRef.current?.close(), []);

  async function startEpisode(body: unknown): Promise<void> {
    setError("");
    sourceRef.current?.close();
    setTicks([]);
    setCursor(0);
    const post = await fetch("/episode", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!post.ok) {
      setError(await post.text());
      return;
    }
    const created = (await post.json()) as {
      episode_id: string;
      faults: Readonly<Record<string, unknown>>[];
    };
    setEpisodeId(created.episode_id);
    setFaults(created.faults.map(toFaultSpec));
    const rows: TickRow[] = [];
    const src = new EventSource(`/stream?episode_id=${created.episode_id}`);
    sourceRef.current = src;
    src.addEventListener("tick", (msg) => {
      const tick = JSON.parse((msg as MessageEvent).data) as {
        step: number;
        states: string[];
        events_at_k: TwinEvent[];
      };
      rows.push({ step: tick.step, states: tick.states, events: tick.events_at_k });
      if (rows.length >= 300) {
        src.close();
        setTicks([...rows].sort((a, b) => a.step - b.step));
      }
    });
  }

  const row = ticks[cursor] ?? null;
  const states = useMemo(() => stateMap(row), [row]);
  const eventsUpToCursor = useMemo(
    () => ticks.slice(0, cursor + 1).flatMap((r) => r.events),
    [ticks, cursor],
  );

  return (
    <main>
      <h1>Events + overlay (T9 harness)</h1>
      <div>
        <label>
          Seed <input data-testid="seed-input" value={seed} onChange={(e) => setSeed(e.target.value)} />
        </label>
        <button
          data-testid="new-f21"
          onClick={() =>
            startEpisode({
              seed: Number(seed),
              faults: [{ class: "drift", origin: "B5", t0: 150, dur: 12, mag_sigma: 5.2 }],
            })
          }
        >
          F-21 drift@B5
        </button>
        <button
          data-testid="new-breakdown"
          onClick={() =>
            startEpisode({
              seed: Number(seed),
              faults: [{ class: "breakdown", origin: "B5", t0: 150, dur: 12, extra: { mttr_mult: 2.0 } }],
            })
          }
        >
          Breakdown@B5 x2
        </button>
      </div>
      <div data-testid="episode-id">{episodeId}</div>
      <div data-testid="form-error">{error}</div>
      <div>
        <label>
          Step{" "}
          <input
            data-testid="step-scrub"
            type="range"
            min={0}
            max={299}
            value={cursor}
            onChange={(e) => setCursor(Number(e.target.value))}
          />
        </label>
        <span data-testid="cursor">
          Step {row?.step ?? 0} / {ticks.length}
        </span>
      </div>
      <section aria-label="overlay preview" style={{ height: 220 }}>
        <ReactFlowProvider>
          <PreviewFlow cursor={cursor} faults={faults} states={states} />
        </ReactFlowProvider>
      </section>
      <section aria-label="gt probe">
        {PROBE_MACHINES.map((id) => {
          const a = anomalyFor(id, row?.step ?? 0, faults, states);
          return (
            <div
              key={id}
              data-testid={`gt-probe-${id}`}
              data-gt={a.gt ? "true" : "false"}
              data-down={a.down ?? ""}
              data-neighbor={a.neighbor ? "true" : "false"}
              data-state={states[id] ?? ""}
            >
              {id} gt={String(a.gt)} down={a.down ?? "-"} neighbor={String(a.neighbor)}
            </div>
          );
        })}
      </section>
      <section aria-label="down style probe">
        <EventFeed events={STYLE_PROBE} cap={10} testId="down-style-probe" />
      </section>
      <section aria-label="global feed">
        <EventFeed events={eventsUpToCursor} />
      </section>
      <section aria-label="per-machine feed">
        <label>
          Machine{" "}
          <select data-testid="machine-select" value={machine} onChange={(e) => setMachine(e.target.value)}>
            {ROSTER.map((id) => (
              <option key={id} value={id}>
                {id}
              </option>
            ))}
          </select>
        </label>
        <MachineEventFeed events={eventsUpToCursor} machineId={machine} />
      </section>
    </main>
  );
}

function PreviewFlow({
  cursor,
  faults,
  states,
}: {
  readonly cursor: number;
  readonly faults: readonly FaultSpec[];
  readonly states: Readonly<Record<string, string>>;
}): React.JSX.Element {
  const step = cursor;
  const nodes = useMemo(
    () =>
      ["B4", "B5", "B6"].map((id, i) => ({
        id,
        type: "machine",
        position: { x: i * 160, y: 60 },
        data: { label: id, kind: "machine" as const, anomaly: anomalyFor(id, step, faults, states) },
      })),
    [step, faults, states],
  );
  return <ReactFlow nodes={nodes} edges={[]} nodeTypes={{ machine: MachineNode }} fitView />;
}

const rootEl = document.getElementById("root");
if (rootEl === null) throw new Error("missing #root element");
createRoot(rootEl).render(
  <StrictMode>
    <Harness />
  </StrictMode>,
);
