import type { TickPatch } from "../topology/TopologyView";
import type { DownUpEvent, TwinEvent } from "../components/events/types";
import { MACHINE_IDS } from "../store/tick";

// Live tick arrays replay in sorted(record["machines"]) order (schema.py
// _machines). The twin roster sorts lexicographically to A0,A1,A2,A7,A8,A9,
// ASM0,ASM1,ASM2, B0,B1,B2,B7P,B7S,B8,B9, C0,C1,C2,C6,C7, INSP0, PKG0,PKG1,
// PKG2, RWK0 — NOT the display order in MACHINE_IDS (PKG0-2 sit after INSP0,
// INSP0 after C7; ASM0-2 sort before B0 within the A-block).
export const STREAM_MACHINE_ORDER: readonly string[] = [...MACHINE_IDS].sort();

export const T_TOTAL = 300;
export const BYTE_BUDGET = 2 * 1024 * 1024;

export interface LiveTick {
  readonly step: number;
  readonly states: readonly string[];
  readonly throughput: readonly number[];
  readonly currents: readonly number[];
  readonly raw?: string;
}

export interface StreamHandle {
  addEventListener(type: string, fn: (ev: { readonly data: string }) => void): void;
  close(): void;
}

export type OpenStream = (url: string) => StreamHandle;

export function streamUrl(base: string, episodeId: string, fromStep = 0): string {
  const q = `episode_id=${encodeURIComponent(episodeId)}${fromStep > 0 ? `&from_step=${fromStep}` : ""}`;
  return `${base}/stream?${q}`;
}

function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

// Live/topology subset is intentional: parseLiveTick gates the four
// per-step channels the stream replays (step/states/throughput/currents)
// and toPatch forwards only step/states/tput because TopologyView.tsx:25
// consumes exactly that 9-key-subset TickPatch (states + tput by machine
// id). Currents stay on LiveTick/panelTick for panels — topology never
// reads them, so they are not forwarded into the patch.
export function parseLiveTick(data: unknown): LiveTick | null {
  if (!isRecord(data)) return null;
  const step = data["step"];
  const states = data["states"];
  const throughput = data["throughput"];
  const currents = data["currents"];
  if (typeof step !== "number" || !Number.isInteger(step) || step < 0 || step >= T_TOTAL) return null;
  if (!Array.isArray(states) || states.length !== STREAM_MACHINE_ORDER.length) return null;
  if (!Array.isArray(throughput) || throughput.length !== STREAM_MACHINE_ORDER.length) return null;
  if (!Array.isArray(currents) || currents.length !== STREAM_MACHINE_ORDER.length) return null;
  const amps = currents.map(Number);
  if (amps.some((v) => !Number.isFinite(v) || v < 0)) return null;
  return { step, states: states.map(String), throughput: throughput.map(Number), currents: amps, raw: "" };
}

export function toPatch(row: LiveTick, order: readonly string[] = STREAM_MACHINE_ORDER): TickPatch {  const states: Record<string, string> = {};
  const tput: Record<string, number> = {};
  for (let i = 0; i < order.length; i += 1) {
    const id = order[i];
    if (id === undefined) continue;
    states[id] = String(row.states[i]);
    tput[id] = Number(row.throughput[i]);
  }
  return { step: row.step, states, tput };
}

export function parseFeedEvents(data: unknown): TwinEvent[] {
  if (!isRecord(data)) return [];
  const list = data["events_at_k"];
  if (!Array.isArray(list)) return [];
  const out: TwinEvent[] = [];
  for (const item of list) {
    if (!isRecord(item)) continue;
    const { event, t, machine, detail } = item;
    if (typeof event !== "string" || typeof t !== "number" || typeof machine !== "string") continue;
    if (!isRecord(detail)) continue;
    if (event === "DOWN" || event === "UP") {
      const { natural, gt_excluded, fault_id } = item;
      if (typeof natural !== "boolean" || typeof gt_excluded !== "boolean") continue;
      if (typeof fault_id !== "string" && fault_id !== null) continue;
      const edge: DownUpEvent = { event, t, machine, detail, natural, gt_excluded, fault_id };
      out.push(edge);
    } else {
      out.push({ event, t, machine, detail });
    }
  }
  return out;
}
