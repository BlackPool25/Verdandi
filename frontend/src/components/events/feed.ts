// T9-owned pure feed logic (filter/cap/label). The .tsx layer stays thin:
// list rendering + ! glyph + family filter select only.
//
// FE-6: unknown channel-7 families are an explicit anomaly state, never a
// silent drop and never rendered as OK. `familyOf` never throws (unknowns
// map to UNKNOWN_FAMILY), `warnUnknown` logs fresh unknown names, and the
// header renders the unknown count via `summarizeFeedAnomalies`. The summary
// shape doubles as the dossier coordination contract: the dossier lane may
// embed it verbatim (no dossier rewrite here).
import { classifyEvent, isDownUp, type EventFamily, type TwinEvent } from "./types";

/** Explicit family attribute for rows classifyEvent rejects. */
export const UNKNOWN_FAMILY = "UNKNOWN" as const;

export type FamilyAttr = EventFamily | typeof UNKNOWN_FAMILY;

export interface FeedFilter {
  readonly machine?: string | undefined;
  readonly family?: string | undefined;
}

/**
 * Non-throwing classify: known names map to their family, anything else
 * maps to UNKNOWN_FAMILY so unknown rows stay visible as explicit states.
 */
export function familyOf(ev: Pick<TwinEvent, "event">): FamilyAttr {
  try {
    return classifyEvent(ev);
  } catch {
    return UNKNOWN_FAMILY;
  }
}

/** True when the event name sits outside the twin allowlist. */
export function isUnknownEvent(ev: Pick<TwinEvent, "event">): boolean {
  return familyOf(ev) === UNKNOWN_FAMILY;
}

/** Row count with unallowlisted names. */
export function countUnknown(events: readonly TwinEvent[]): number {
  let n = 0;
  for (const ev of events) {
    if (isUnknownEvent(ev)) n += 1;
  }
  return n;
}

/** Sorted distinct unallowlisted names (stable header/dossier copy). */
export function unknownNames(events: readonly TwinEvent[]): string[] {
  const names = new Set<string>();
  for (const ev of events) {
    if (isUnknownEvent(ev)) names.add(ev.event);
  }
  return [...names].sort();
}

const warnedUnknownNames = new Set<string>();

/**
 * Log each fresh unknown name once (FE-6: warn, never silent). Returns the
 * unknown row count. Quiet when nothing is unknown.
 */
export function warnUnknown(events: readonly TwinEvent[], scope: string): number {
  const count = countUnknown(events);
  const fresh = unknownNames(events).filter((n) => !warnedUnknownNames.has(n));
  for (const n of fresh) warnedUnknownNames.add(n);
  if (fresh.length > 0) {
    console.warn(
      `event-feed[${scope}]: ${count} row(s) with unknown family ` +
        `(${fresh.join(", ")}) — rendered as explicit ! UNKNOWN, never as OK`,
    );
  }
  return count;
}

/** Test hook: clear the once-per-name warn memory. */
export function resetFeedWarnings(): void {
  warnedUnknownNames.clear();
}

export function filterEvents(events: readonly TwinEvent[], filter: FeedFilter): TwinEvent[] {
  return events.filter((ev) => {
    if (filter.machine !== undefined && ev.machine !== filter.machine) return false;
    if (filter.family !== undefined) {
      if (filter.family === UNKNOWN_FAMILY) return isUnknownEvent(ev);
      if (familyOf(ev) !== filter.family) return false;
    }
    return true;
  });
}

export interface CappedFeed {
  readonly visible: readonly TwinEvent[];
  readonly overflow: number;
}

/**
 * Cap the rendered rows latest-first; overflow feeds the "…+N more" badge
 * counting the hidden older rows.
 */
export function capFeed(events: readonly TwinEvent[], cap: number): CappedFeed {
  if (events.length <= cap) return { visible: events, overflow: 0 };
  return { visible: events.slice(events.length - cap), overflow: events.length - cap };
}

/**
 * One-line row label. DOWN/UP rows always carry the !-glyph kind tag
 * (color never alone): "! FAULT" injected vs "! NATURAL" natural.
 * Unallowlisted rows carry "! UNKNOWN" so they read as anomalies.
 */
export function labelFor(ev: TwinEvent): string {
  const base = `${ev.event} ${ev.machine} t${ev.t}`;
  if (isUnknownEvent(ev)) return `${base} ! UNKNOWN`;
  if (!isDownUp(ev)) return base;
  return `${base} ! ${ev.natural ? "NATURAL" : "FAULT"}`;
}

export interface FeedAnomalySummary {
  readonly total: number;
  readonly visible: number;
  readonly overflow: number;
  readonly unknownCount: number;
  readonly unknownNames: readonly string[];
  /** True when visible + overflow drifts from total: render, never hide. */
  readonly countMismatch: boolean;
}

/**
 * Dossier coordination shape (FE-6): feed-computed anomaly counts the
 * dossier lane may embed verbatim alongside nodes/paths. `countMismatch`
 * is an explicit state — the header renders it instead of trusting the cap.
 */
export function summarizeFeedAnomalies(
  all: readonly TwinEvent[],
  visible: readonly TwinEvent[],
  overflow: number,
): FeedAnomalySummary {
  return {
    total: all.length,
    visible: visible.length,
    overflow,
    unknownCount: countUnknown(all),
    unknownNames: unknownNames(all),
    countMismatch: visible.length + overflow !== all.length,
  };
}
