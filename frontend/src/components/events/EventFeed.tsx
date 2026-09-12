import { useMemo, useState } from "react";
import { capFeed, filterEvents, labelFor } from "./feed";
import { classifyEvent, downKindOf, EVENT_FAMILIES, type TwinEvent } from "./types";
import "./events.css";

export const FEED_CAP_DEFAULT = 100;

export interface EventFeedProps {
  readonly events: readonly TwinEvent[];
  /** Per-machine feed pins this machine; global feed omits it. */
  readonly machineId?: string | undefined;
  readonly cap?: number | undefined;
  readonly testId?: string | undefined;
}

/**
 * Global + per-machine channel-7 feed (T9 owns). DOWN/UP rows render the
 * !-glyph kind tag (! FAULT injected vs ! NATURAL natural) so color is
 * never the only signal. Rows cap at `cap` with a "…+N more" badge.
 */
export function EventFeed(props: EventFeedProps): React.JSX.Element {
  const cap = props.cap ?? FEED_CAP_DEFAULT;
  const [family, setFamily] = useState<string>("ALL");

  const rows = useMemo(() => {
    const filtered = filterEvents(props.events, {
      machine: props.machineId,
      family: family === "ALL" ? undefined : family,
    });
    return capFeed(filtered, cap);
  }, [props.events, props.machineId, family, cap]);

  const testId =
    props.testId ?? (props.machineId === undefined ? "event-feed" : "machine-event-feed");

  return (
    <section data-testid={testId} aria-label={props.machineId ?? "global event feed"}>
      <div>
        <label>
          Family{" "}
          <select
            data-testid="feed-family-filter"
            value={family}
            onChange={(e) => setFamily(e.target.value)}
          >
            <option value="ALL">ALL</option>
            {EVENT_FAMILIES.map((f) => (
              <option key={f} value={f}>
                {f}
              </option>
            ))}
          </select>
        </label>
        {rows.overflow > 0 && (
          <span data-testid="feed-overflow">…+{rows.overflow} more</span>
        )}
      </div>
      <ul className="evt-feed">
        {rows.visible.length === 0 && (
          <li data-testid="feed-empty">No events at this step yet.</li>
        )}
        {rows.visible.map((ev, i) => (
          <FeedRow key={`${ev.t}-${ev.event}-${ev.machine}-${i}`} ev={ev} />
        ))}
      </ul>
    </section>
  );
}

function FeedRow({ ev }: { readonly ev: TwinEvent }): React.JSX.Element {
  const kind = downKindOf(ev);
  const rowClass =
    kind === "injected" ? "evt-row row-down-injected" : kind === "natural" ? "evt-row row-down-natural" : "evt-row";
  return (
    <li
      data-testid="event-row"
      data-event={ev.event}
      data-machine={ev.machine}
      data-family={classifyEvent(ev)}
      data-down-kind={kind ?? ""}
      className={rowClass}
    >
      {labelFor(ev)}
      {kind !== null && (
        <span className="row-kind" data-testid="event-kind-glyph">
          ! {kind === "injected" ? "FAULT" : "NATURAL"}
        </span>
      )}
    </li>
  );
}
