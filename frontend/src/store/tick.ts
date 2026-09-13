export const TICK_KEYS = [
  "step",
  "states",
  "obs",
  "throughput",
  "buffers",
  "sbuf_level",
  "events_at_k",
  "faults",
  "quality",
] as const;

export const MACHINE_IDS = [
  ...Array.from({ length: 10 }, (_, i) => `A${i}`),
  ...Array.from({ length: 10 }, (_, i) => `B${i}`),
  ...Array.from({ length: 8 }, (_, i) => `C${i}`),
  "ASM0",
  "ASM1",
  "ASM2",
  "RWK0",
] as const;

export type MachineId = (typeof MACHINE_IDS)[number];

export const BUFFER_IDS = [
  ...Array.from({ length: 9 }, (_, i) => `A${i}${i + 1}`),
  ...Array.from({ length: 9 }, (_, i) => `B${i}${i + 1}`),
  ...Array.from({ length: 7 }, (_, i) => `C${i}${i + 1}`),
  "ASM01",
  "ASM12",
  "GA9",
  "GB9",
  "RWK_RET",
  "SBUF",
] as const;

export type BufferId = (typeof BUFFER_IDS)[number];

export interface Tick {
  readonly step: number;
  readonly states: readonly string[];
  readonly obs: readonly number[];
  readonly throughput: readonly number[];
  readonly buffers: readonly number[];
  readonly sbuf_level: number;
  readonly events_at_k: readonly unknown[];
  readonly faults: readonly unknown[];
  readonly quality: Readonly<Record<string, unknown>>;
}

export class TickValidationError extends Error {
  readonly tickStep: number | null;
  constructor(message: string, tickStep: number | null = null) {
    super(`tick rejected: ${message}`);
    this.name = "TickValidationError";
    this.tickStep = tickStep;
  }
}

function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

export function parseTick(raw: unknown): Tick {
  if (!isRecord(raw)) throw new TickValidationError("not an object");
  for (const k of TICK_KEYS) {
    if (!(k in raw)) throw new TickValidationError(`missing key ${k}`);
  }
  if ("temperature" in raw || "temp" in raw) {
    throw new TickValidationError("temperature key forbidden (twin discards _temp)");
  }
  const step = raw["step"];
  if (typeof step !== "number" || !Number.isInteger(step) || step < 0) {
    throw new TickValidationError("step must be a non-negative integer", null);
  }
  const states = raw["states"];
  const obs = raw["obs"];
  const throughput = raw["throughput"];
  const buffers = raw["buffers"];
  if (!Array.isArray(states) || states.length !== MACHINE_IDS.length) {
    throw new TickValidationError("states must match machine roster", step);
  }
  if (!Array.isArray(obs) || obs.length !== MACHINE_IDS.length) {
    throw new TickValidationError("obs must match machine roster", step);
  }
  if (!Array.isArray(throughput) || throughput.length !== MACHINE_IDS.length) {
    throw new TickValidationError("throughput must match machine roster", step);
  }
  if (!Array.isArray(buffers) || buffers.length !== BUFFER_IDS.length) {
    throw new TickValidationError("buffers must match buffer roster", step);
  }
  for (const v of throughput) {
    if (v !== 0 && v !== 1) throw new TickValidationError("throughput domain is {0,1}", step);
  }
  for (const v of obs) {
    if (typeof v !== "number" || !Number.isFinite(v)) {
      throw new TickValidationError("obs must be finite numbers", step);
    }
  }
  const events = raw["events_at_k"];
  const faults = raw["faults"];
  const quality = raw["quality"];
  if (!Array.isArray(events) || !Array.isArray(faults) || !isRecord(quality)) {
    throw new TickValidationError("events/faults/quality shape", step);
  }
  const sbuf = raw["sbuf_level"];
  if (typeof sbuf !== "number" || !Number.isFinite(sbuf)) {
    throw new TickValidationError("sbuf_level must be finite", step);
  }
  return {
    step,
    states: states.map(String),
    obs: obs.map(Number),
    throughput: throughput.map(Number),
    buffers: buffers.map(Number),
    sbuf_level: sbuf,
    events_at_k: events,
    faults,
    quality,
  };
}
