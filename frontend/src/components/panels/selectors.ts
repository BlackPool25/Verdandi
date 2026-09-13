// T8 pure selectors: panel values derive from the tick payload row only.
// No React here so vitest can assert payload equality directly.
import {
  BUFFER_CAPS,
  MACHINE_META,
  NEVER_DIVERT_CLASSES,
  SBUF_CAP,
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
      readonly meta: { readonly class: string; readonly base: number; readonly sigma: number; readonly cycle: number; readonly mttf: number; readonly mttr: number; readonly bufferCap: number | null };
      readonly envelope: Envelope;
      readonly envelopeNote: "base±3σ, clamp ±6σ";
      readonly tailPath: TailPath;
      readonly sections: readonly MachineConfigSection[];
      readonly rawJson: string;
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

// Honest per-tick line aggregates: pure sums/counts over the payload row.
// No rates, no availability math — just what the tick says.
export interface LineStats {
  readonly tputSum: number;
  readonly run: number;
  readonly blocked: number;
  readonly starved: number;
  readonly down: number;
  readonly meanObs: number;
  readonly sbufLevel: number;
  readonly sbufHigh: boolean;
}

export function lineStatsFor(tick: PanelTick): LineStats {
  let tputSum = 0;
  let run = 0;
  let blocked = 0;
  let starved = 0;
  let down = 0;
  let obsSum = 0;
  for (const v of tick.throughput) tputSum += v;
  for (const s of tick.states) {
    if (s === "RUN") run += 1;
    else if (s === "BLOCKED") blocked += 1;
    else if (s === "STARVED") starved += 1;
    else if (s === "DOWN") down += 1;
  }
  for (const v of tick.obs) obsSum += v;
  return {
    tputSum,
    run,
    blocked,
    starved,
    down,
    meanObs: tick.obs.length > 0 ? obsSum / tick.obs.length : 0,
    sbufLevel: tick.sbuf_level,
    sbufHigh: tick.sbuf_level >= SBUF_HIGH,
  };
}

// Honest episode finals: twin run_episode sbuf_stats/flow_stats verbatim.
// Missing header or missing key → null, never a fabricated zero.
export interface EpisodeHeader {
  readonly sbuf_stats?: Readonly<Record<string, unknown>> | null | undefined;
  readonly flow_stats?: Readonly<Record<string, unknown>> | null | undefined;
  readonly c7tail_final?: unknown;
}

export interface EpisodeStats {
  readonly diverted: number | null;
  readonly drained: number | null;
  readonly sbufMax: number | null;
  readonly sunk: number | null;
  readonly scrapped: number | null;
  readonly rejected: number | null;
  readonly reworked: number | null;
  readonly c7tailFinal: number | null;
}

function asFinite(v: unknown): number | null {
  return typeof v === "number" && Number.isFinite(v) ? v : null;
}

export function episodeStatsFor(header: EpisodeHeader | null | undefined): EpisodeStats {
  const sbuf = header?.sbuf_stats ?? null;
  const flow = header?.flow_stats ?? null;
  const top = asFinite(header?.c7tail_final);
  const nested =
    flow !== null && typeof flow === "object" ? asFinite(flow["c7tail"]) : null;
  return {
    diverted:
      sbuf !== null && typeof sbuf === "object" ? asFinite(sbuf["diverted"]) : null,
    drained:
      sbuf !== null && typeof sbuf === "object" ? asFinite(sbuf["drained"]) : null,
    sbufMax:
      sbuf !== null && typeof sbuf === "object" ? asFinite(sbuf["max_occupancy"]) : null,
    sunk: flow !== null && typeof flow === "object" ? asFinite(flow["sunk"]) : null,
    scrapped:
      flow !== null && typeof flow === "object" ? asFinite(flow["scrapped"]) : null,
    rejected:
      flow !== null && typeof flow === "object" ? asFinite(flow["rejected"]) : null,
    reworked:
      flow !== null && typeof flow === "object" ? asFinite(flow["reworked"]) : null,
    c7tailFinal: top ?? nested,
  };
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
  const lo3 = meta.base - 3 * meta.sigma;
  const hi3 = meta.base + 3 * meta.sigma;
  const clampLo6 = meta.base - 6 * meta.sigma;
  const clampHi6 = meta.base + 6 * meta.sigma;
  const tailPath = tailPathFor(id);
  const sections: readonly MachineConfigSection[] = [
    {
      heading: "class",
      rows: [{ label: "class", value: meta.cls, testId: "machine-panel-class" }],
    },
    {
      heading: "signal",
      rows: [
        { label: "base", value: `${meta.base} units`, testId: "machine-panel-base" },
        { label: "sigma", value: `${meta.sigma} units`, testId: "machine-panel-sigma" },
        { label: "envelope ±3σ", value: `${lo3} – ${hi3} units`, testId: "machine-panel-envelope-3s" },
        { label: "clamp ±6σ", value: `${clampLo6} – ${clampHi6} units`, testId: "machine-panel-envelope-6s" },
      ],
    },
    {
      heading: "timing",
      rows: [{ label: "cycle", value: `${meta.cycle} steps`, testId: "machine-panel-cycle-full" }],
    },
    {
      heading: "reliability",
      rows: [
        { label: "mttf", value: `${meta.mttf} steps`, testId: "machine-panel-mttf-full" },
        { label: "mttr", value: `${meta.mttr} steps`, testId: "machine-panel-mttr-full" },
      ],
    },
    {
      heading: "buffer & routing",
      rows: [
        { label: "buffer cap", value: meta.bufferCap === null ? "none (store-fed)" : `${meta.bufferCap} parts`, testId: "machine-panel-buffer-cap" },
        { label: "tail path", value: tailPath, testId: "machine-panel-path-full" },
      ],
    },
  ];
  const rawJson = JSON.stringify({ id, ...meta, lo3, hi3, clampLo6, clampHi6, tailPath });
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
      bufferCap: meta.bufferCap,
    },
    envelope: {
      lo3,
      hi3,
      clampLo6,
      clampHi6,
    },
    envelopeNote: "base±3σ, clamp ±6σ",
    tailPath,
    sections,
    rawJson,
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

// SBUF store faceplate values: level/cap verbatim from the tick payload,
// high-util ⇔ level ≥ 80% of cap (twin _SBUF_HIGH = 24 of 30). SBUF is a
// store, not a machine — no obs/tput series, no machinePanelFor row.
export interface SbufPanel {
  readonly id: "SBUF";
  readonly level: number;
  readonly cap: number;
  readonly high: boolean;
  readonly noSeriesLabel: "no per-step series";
}

export function sbufPanelFor(tick: PanelTick): SbufPanel {
  return {
    id: "SBUF",
    level: tick.sbuf_level,
    cap: SBUF_CAP,
    high: tick.sbuf_level >= SBUF_HIGH,
    noSeriesLabel: "no per-step series",
  };
}

// Tail/AGV routing legend: tails ride the AGV path, never SBUF-direct;
// feed/form classes never divert (twin SBUF guard).
export type TailPath = "AGV" | "SBUF-eligible" | "never-diverts" | "unknown";

// T4 full per-kind config: readable dl sections built verbatim from
// MACHINE_META (T1 cls key) + envelope base±3σ/±6σ. One section per
// concern; values carry units so all 9 sprite classes render distinct.
export interface MachineConfigRow {
  readonly label: string;
  readonly value: string;
  readonly testId: string;
}

export interface MachineConfigSection {
  readonly heading: string;
  readonly rows: readonly MachineConfigRow[];
}

export function tailPathFor(id: string): TailPath {
  if ((TAILS as readonly string[]).includes(id)) return "AGV";
  const meta = MACHINE_META[id];
  if (meta === undefined) return "unknown";
  if ((NEVER_DIVERT_CLASSES as readonly string[]).includes(meta.cls)) {
    return "never-diverts";
  }
  return "SBUF-eligible";
}
