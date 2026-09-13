// T9-owned channel-7 event types (SIM_SPEC section 8, twin lines 402-454).
// Mirrors services/sim_bridge/schema.py EVENT_FAMILIES; the bridge stays the
// contract owner, this module only re-states the allowlist for display.

export const EVENT_NAMES = [
  "FAULT_START",
  "FAULT_END",
  "BLOCK_ON",
  "BLOCK_OFF",
  "STARVE_ON",
  "STARVE_OFF",
  "DOWN",
  "UP",
  "DIVERT_SBUF",
  "AGV_WAIT",
  "REJECT_ROUTE",
] as const;

export type EventName = (typeof EVENT_NAMES)[number];

export const EVENT_FAMILIES = [
  "FAULT",
  "BLOCK",
  "STARVE",
  "DOWN_UP",
  "AGV_WAIT",
  "REJECT_ROUTE",
  "DIVERT_SBUF",
] as const;

export type EventFamily = (typeof EVENT_FAMILIES)[number];

const EVENT_TO_FAMILY: Record<EventName, EventFamily> = {
  FAULT_START: "FAULT",
  FAULT_END: "FAULT",
  BLOCK_ON: "BLOCK",
  BLOCK_OFF: "BLOCK",
  STARVE_ON: "STARVE",
  STARVE_OFF: "STARVE",
  DOWN: "DOWN_UP",
  UP: "DOWN_UP",
  AGV_WAIT: "AGV_WAIT",
  REJECT_ROUTE: "REJECT_ROUTE",
  DIVERT_SBUF: "DIVERT_SBUF",
};

/** Base channel-7 shape {event, t, machine, detail} for every variant. */
export interface TwinEvent {
  readonly event: string;
  readonly t: number;
  readonly machine: string;
  readonly detail: Readonly<Record<string, unknown>>;
}

/**
 * DOWN/UP edge carrying the disambiguation trio as top-level keys
 * (twin _transition lines 428-454). No other family carries these keys.
 */
export interface DownUpEvent extends TwinEvent {
  readonly event: "DOWN" | "UP";
  /** True = natural breakdown edge (GT-excluded); false = injected fault. */
  readonly natural: boolean;
  readonly gt_excluded: boolean;
  /** Fault id when injected, null when natural. */
  readonly fault_id: string | null;
}

export type DownKind = "natural" | "injected";

export function classifyEvent(ev: Pick<TwinEvent, "event">): EventFamily {
  const fam = (EVENT_TO_FAMILY as Readonly<Record<string, EventFamily>>)[ev.event];
  if (fam === undefined) throw new Error(`unknown event family for event=${ev.event}`);
  return fam;
}

export function isDownUp(ev: TwinEvent): ev is DownUpEvent {
  return ev.event === "DOWN" || ev.event === "UP";
}

/**
 * DOWN/UP disambiguation for display: natural (dashed style) vs injected
 * (solid fault style). Non-DOWN/UP events return null.
 */
export function downKindOf(ev: TwinEvent): DownKind | null {
  if (!isDownUp(ev)) return null;
  return ev.natural ? "natural" : "injected";
}

/** Fault spec subset the overlay needs (from tick `faults` / header). */
export interface FaultSpec {
  readonly id: string;
  readonly class: string;
  readonly origin: string;
  readonly t0: number;
  readonly dur: number;
  readonly t1: number;
  readonly mttr_mult?: number | undefined;
}
