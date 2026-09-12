// T8 pure selectors: panel values derive from the tick payload row only.
// No React here so vitest can assert payload equality directly.
import {
  BUFFER_CAPS,
  MACHINE_META,
  NEVER_DIVERT_CLASSES,
  SBUF_HIGH,
  TAILS,
} from "./machineMeta";

export interface PanelTick {
  readonly step: number;
  readonly states: readonly string[];
  readonly obs: readonly number[];
  readonly throughput: readonly number[];
  readonly buffers: readonly number[];
  readonly sbuf_level: number;
  readonly quality: Readonly<Record<string, unknown>>;
  readonly machineOrder: readonly string[];
  readonly bufferOrder: readonly string[];
  readonly c7tailFinal?: number | null;
}

export interface Envelope {
  readonly lo3: number;
  readonly hi3: number;
  readonly clampLo6: number;
  readonly clampHi6: number;
}

export type MachinePanel =
  | { readonly found: false; readonly id: string }
  | {
      readonly found: true;
      readonly kind: "machine";
      readonly id: string;
      readonly state: string;
      readonly obs: number;
      readonly tput: number;
      readonly flag: unknown;
      readonly meta: { readonly class: string; readonly base: number; readonly sigma: number; readonly cycle: number; readonly mttf: number; readonly mttr: number };
      readonly envelope: Envelope;
      readonly envelopeNote: "base±3σ, clamp ±6σ";
      readonly c7tailFinal?: undefined;
      readonly noSeriesLabel?: undefined;
    }
  | {
      readonly found: true;
      readonly kind: "c7tail";
      readonly id: "_C7TAIL";
      readonly c7tailFinal: number | null;
      readonly noSeriesLabel: "no per-step series";
    };

export interface BufferBar {
  readonly id: string;
  readonly level: number;
  readonly cap: number;
  readonly util: number;
  readonly high: boolean;
}

export function machinePanelFor(tick: PanelTick, id: string): MachinePanel {
  if (id === "_C7TAIL") {
    return {
      found: true,
      kind: "c7tail",
      id: "_C7TAIL",
      c7tailFinal: tick.c7tailFinal ?? null,
      noSeriesLabel: "no per-step series",
    };
  }
  const i = tick.machineOrder.indexOf(id);
  const meta = MACHINE_META[id];
  if (i < 0 || meta === undefined) return { found: false, id };
  const state = tick.states[i];
  const obs = tick.obs[i];
  const tput = tick.throughput[i];
  if (state === undefined || obs === undefined || tput === undefined) {
    return { found: false, id };
  }
  return {
    found: true,
    kind: "machine",
    id,
    state,
    obs,
    tput,
    flag: tick.quality[id] ?? "no completed part yet",
    meta: {
      class: meta.cls,
      base: meta.base,
      sigma: meta.sigma,
      cycle: meta.cycle,
      mttf: meta.mttf,
      mttr: meta.mttr,
    },
    envelope: {
      lo3: meta.base - 3 * meta.sigma,
      hi3: meta.base + 3 * meta.sigma,
      clampLo6: meta.base - 6 * meta.sigma,
      clampHi6: meta.base + 6 * meta.sigma,
    },
    envelopeNote: "base±3σ, clamp ±6σ",
  };
}

export function bufferBarsFor(tick: PanelTick): BufferBar[] {
  return tick.bufferOrder.map((id, j) => {
    const cap = BUFFER_CAPS[id] ?? 0;
    const level = tick.buffers[j] ?? 0;
    return {
      id,
      level,
      cap,
      util: cap > 0 ? level / cap : 0,
      // SBUF high-util ⇔ level ≥ 80% of cap (twin _SBUF_HIGH = 24 of 30).
      high: id === "SBUF" ? level >= SBUF_HIGH : false,
    };
  });
}

// Tail/AGV routing legend: tails ride the AGV path, never SBUF-direct;
// feed/form classes never divert (twin SBUF guard).
export type TailPath = "AGV" | "SBUF-eligible" | "never-diverts" | "unknown";

export function tailPathFor(id: string): TailPath {
  if ((TAILS as readonly string[]).includes(id)) return "AGV";
  const meta = MACHINE_META[id];
  if (meta === undefined) return "unknown";
  if ((NEVER_DIVERT_CLASSES as readonly string[]).includes(meta.cls)) {
    return "never-diverts";
  }
  return "SBUF-eligible";
}
