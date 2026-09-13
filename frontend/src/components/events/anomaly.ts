// T9-owned anomaly overlay semantics (twin _inj_down + GT-exclusion).
//
// - Breakdown marker uses the GT window [t0,t1) (fault t1 = t0+dur).
// - Extended DOWN [t0,t0+ceil(dur*mult)) is shown as DOWN-state duration,
//   never as GT. For non-breakdown faults mult is 1.0, so both agree.
// - Neighbor highlight is depth-1 ONLY: a direct-buffer neighbor (shares a
//   buffer edge with the origin) whose same-step state is BLOCKED/STARVED.
//   No deeper rings, no path search.

import { PINNED_EDGES } from "../../topology/edges";
import type { DownKind, FaultSpec } from "./types";

export interface StepWindow {
  readonly t0: number;
  readonly t1: number;
}

/**
 * Normalize one bridge fault entry to a FaultSpec. POST /episode echoes
 * the validated fault (no t1, mult nested under extra) while tick/header
 * faults are materialized specs (t1 + top-level mttr_mult): accept both.
 */
export function toFaultSpec(raw: Readonly<Record<string, unknown>>): FaultSpec {
  const extra = (raw["extra"] as Readonly<Record<string, unknown>> | undefined) ?? {};
  const t0 = Number(raw["t0"]);
  const dur = Number(raw["dur"]);
  const t1 = raw["t1"] === undefined ? t0 + dur : Number(raw["t1"]);
  const mult = raw["mttr_mult"] === undefined ? (extra["mttr_mult"] as number | undefined) : Number(raw["mttr_mult"]);
  return {
    id: String(raw["id"]),
    class: String(raw["class"]),
    origin: String(raw["origin"]),
    t0,
    dur,
    t1,
    mttr_mult: mult,
  };
}

/** GT window of one fault spec: [t0,t1). */
export function gtWindowOf(fault: FaultSpec): StepWindow {
  return { t0: fault.t0, t1: fault.t1 };
}

/**
 * Extended DOWN window of one breakdown spec: [t0,t0+ceil(dur*mult)).
 * Mirrors twin _inj_down. Non-breakdown faults carry mult 1.0 (dur only).
 */
export function downWindowOf(fault: FaultSpec): StepWindow {
  if (fault.class !== "breakdown") return { t0: fault.t0, t1: fault.t1 };
  const mult = fault.mttr_mult ?? 1.0;
  return { t0: fault.t0, t1: fault.t0 + Math.ceil(fault.dur * mult) };
}

/** Origin outlined while step sits inside its GT window [t0,t1). */
export function isGtOutline(machine: string, step: number, faults: readonly FaultSpec[]): boolean {
  return faults.some((f) => f.origin === machine && f.t0 <= step && step < f.t1);
}

/**
 * DOWN-state duration at (machine, step): true while a breakdown extended
 * window covers an injected DOWN, or the live state reads DOWN (natural).
 * GT windows alone never imply DOWN (drift/bias faults hold no DOWN).
 */
export function isDownState(
  machine: string,
  step: number,
  faults: readonly FaultSpec[],
  state: string | undefined,
): boolean {
  if (
    faults.some((f) => {
      if (f.origin !== machine || f.class !== "breakdown") return false;
      const w = downWindowOf(f);
      return w.t0 <= step && step < w.t1;
    })
  ) {
    return true;
  }
  return state === "DOWN";
}

/**
 * DOWN disambiguation for display: injected while a breakdown extended
 * window covers the machine, else natural when the live state is DOWN.
 * A natural DOWN inside somebody else's GT window stays natural and never
 * earns the fault outline (GT-exclusion: twin lines 508-512).
 */
export function downKindFor(
  machine: string,
  step: number,
  faults: readonly FaultSpec[],
  state: string | undefined,
): DownKind | null {
  const injected = faults.some((f) => {
    if (f.origin !== machine || f.class !== "breakdown") return false;
    const w = downWindowOf(f);
    return w.t0 <= step && step < w.t1;
  });
  if (injected) return "injected";
  if (state === "DOWN") return "natural";
  return null;
}

// Direct-buffer neighbors: machines sharing one buffer edge. AGV-drain
// edges ride the AGV path (no shared buffer), so they are excluded.
const BUFFER_EDGE_CLASSES: ReadonlySet<string> = new Set([
  "line-gap",
  "assembly",
  "rework",
  "tail-stage",
]);

const NEIGHBOR_MAP: ReadonlyMap<string, ReadonlySet<string>> = (() => {
  const adj = new Map<string, Set<string>>();
  const link = (a: string, b: string): void => {
    if (a === b) return;
    let sa = adj.get(a);
    if (sa === undefined) {
      sa = new Set();
      adj.set(a, sa);
    }
    sa.add(b);
    let sb = adj.get(b);
    if (sb === undefined) {
      sb = new Set();
      adj.set(b, sb);
    }
    sb.add(a);
  };
  for (const e of PINNED_EDGES) {
    if (BUFFER_EDGE_CLASSES.has(e.data.edgeClass)) link(e.source, e.target);
  }
  return adj;
})();

/** Depth-1 direct-buffer neighbors of one machine (empty when isolated). */
export function neighborsOf(machine: string): ReadonlySet<string> {
  return NEIGHBOR_MAP.get(machine) ?? new Set();
}

/**
 * Neighbor highlight: machine is a depth-1 neighbor of a GT-outlined origin
 * AND its same-step state is BLOCKED or STARVED. RUN/DOWN neighbors stay
 * plain; machines two hops out are never highlighted.
 */
export function neighborHighlightFor(
  machine: string,
  step: number,
  faults: readonly FaultSpec[],
  states: Readonly<Record<string, string>>,
): boolean {
  const state = states[machine];
  if (state !== "BLOCKED" && state !== "STARVED") return false;
  for (const n of neighborsOf(machine)) {
    if (isGtOutline(n, step, faults)) return true;
  }
  return false;
}

export interface AnomalyDatum {
  readonly gt: boolean;
  readonly neighbor: boolean;
  readonly down: DownKind | null;
}

/**
 * Single overlay seam for T10: per-tick MachineNode datum for one machine.
 * Feed through updateNodeData alongside state/tput; TopologyView untouched.
 */
export function anomalyFor(
  machine: string,
  step: number,
  faults: readonly FaultSpec[],
  states: Readonly<Record<string, string>>,
): AnomalyDatum {
  return {
    gt: isGtOutline(machine, step, faults),
    neighbor: neighborHighlightFor(machine, step, faults, states),
    down: downKindFor(machine, step, faults, states[machine]),
  };
}
