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
  "currents",
] as const;

// 26-machine topology-A roster in MACHINE_INDEX order (mirrors
// src/config.py + topology/nodes.ts). The 32-machine v1 roster is retired.
export const MACHINE_IDS = [
  "A0", "A1", "A2", "A7", "A8", "A9",
  "B0", "B1", "B2", "B7P", "B7S", "B8", "B9",
  "C0", "C1", "C2", "C6", "C7",
  "PKG0", "PKG1", "PKG2",
  "ASM0", "ASM1", "INSP0", "ASM2", "RWK0",
] as const;

export type MachineId = (typeof MACHINE_IDS)[number];

export const BUFFER_IDS = [
  "A01", "A12", "A27", "A78", "A89",
  "B01", "B12", "B2B7P", "B2B7S", "B7PB8", "B7SB8", "B89",
  "C01", "C12", "C26", "C67",
  "ASM01", "INSP01", "INSP02", "GA9", "GB9",
  "C7PKG", "PKG01", "PKG02",
  "RWK_RET", "SBUF",
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
  readonly currents: readonly number[];
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
  const currents = raw["currents"];
  if (!Array.isArray(currents) || currents.length !== MACHINE_IDS.length) {
    throw new TickValidationError("currents must match machine roster", step);
  }
  for (const v of currents) {
    if (typeof v !== "number" || !Number.isFinite(v) || v < 0) {
      throw new TickValidationError("currents must be finite numbers >= 0", step);
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
    currents: currents.map(Number),
  };
}
