// T9-owned pure feed logic (filter/cap/label). The .tsx layer stays thin:
// list rendering + ! glyph + family filter select only.
import { classifyEvent, isDownUp, type TwinEvent } from "./types";

export interface FeedFilter {
  readonly machine?: string | undefined;
  readonly family?: string | undefined;
}

export function filterEvents(events: readonly TwinEvent[], filter: FeedFilter): TwinEvent[] {
  return events.filter((ev) => {
    if (filter.machine !== undefined && ev.machine !== filter.machine) return false;
    if (filter.family !== undefined && classifyEvent(ev) !== filter.family) return false;
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
 */
export function labelFor(ev: TwinEvent): string {
  const base = `${ev.event} ${ev.machine} t${ev.t}`;
  if (!isDownUp(ev)) return base;
  return `${base} ! ${ev.natural ? "NATURAL" : "FAULT"}`;
}
