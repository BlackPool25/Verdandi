import type { TickPatch } from "../topology/TopologyView";
import type { DownUpEvent, TwinEvent } from "../components/events/types";
import { MACHINE_IDS } from "../store/tick";

// Live tick arrays replay in sorted(record["machines"]) order (schema.py
// _machines). The twin roster sorts lexicographically to A0-A9, ASM0-2,
// B0-B9, C0-C7, RWK0 — NOT the display order in MACHINE_IDS.
export const STREAM_MACHINE_ORDER: readonly string[] = [...MACHINE_IDS].sort();

export const T_TOTAL = 300;
export const BYTE_BUDGET = 2 * 1024 * 1024;

export interface LiveTick {
  readonly step: number;
  readonly states: readonly string[];
  readonly throughput: readonly number[];
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

export function parseLiveTick(data: unknown): LiveTick | null {
  if (!isRecord(data)) return null;
  const step = data["step"];
  const states = data["states"];
  const throughput = data["throughput"];
  if (typeof step !== "number" || !Number.isInteger(step) || step < 0 || step >= T_TOTAL) return null;
  if (!Array.isArray(states) || states.length !== STREAM_MACHINE_ORDER.length) return null;
  if (!Array.isArray(throughput) || throughput.length !== STREAM_MACHINE_ORDER.length) return null;
  return { step, states: states.map(String), throughput: throughput.map(Number), raw: "" };
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
