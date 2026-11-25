import { memo, useMemo, useState } from "react";
import { capFeed, familyOf, filterEvents, labelFor, summarizeFeedAnomalies, UNKNOWN_FAMILY, warnUnknown } from "./feed";
import { downKindOf, EVENT_FAMILIES, type TwinEvent } from "./types";
import { findStepGaps, gapRangeLabel, type StepGap } from "../charts/gaps";
import "./events.css";
import "./feed-gaps.css";

export const FEED_CAP_DEFAULT = 100;

export interface EventFeedProps {
  readonly events: readonly TwinEvent[];
  /** Per-machine feed pins this machine; global feed omits it. */
  readonly machineId?: string | undefined;
  readonly cap?: number | undefined;
  readonly testId?: string | undefined;
  /**
   * FE-11 covered-step sequence backing gap rows. Wherever these steps
   * are non-contiguous a ⚠ gap row is interleaved at the right position.
   * Omitted (sparse events are normal traffic) renders no markers.
   */
  readonly steps?: readonly number[] | undefined;
}

interface FeedGapItem {
  readonly kind: "gap";
  readonly gap: StepGap;
}

interface FeedEventItem {
  readonly kind: "event";
  readonly ev: TwinEvent;
}

type FeedItem = FeedGapItem | FeedEventItem;

/**
 * Interleave gap markers into capped rows: a gap covering steps
 * (from..to) is placed before the first visible row at or past `to`,
 * so it sits exactly where the missing steps would have rendered.
 * Gaps fully outside the visible window are skipped.
 */
export function interleaveFeedGaps(
  visible: readonly TwinEvent[],
  gaps: readonly StepGap[],
): FeedItem[] {
  if (gaps.length === 0) return visible.map((ev) => ({ kind: "event" as const, ev }));
  const firstT = visible.length > 0 ? (visible[0]?.t ?? 0) : 0;
  const sorted = [...gaps]
    // Gaps fully hidden above the capped window stay hidden with the
    // overflow rows ("…+N more" already accounts for that region).
    .filter((gap) => visible.length === 0 || gap.to > firstT)
    .sort((a, b) => a.from - b.from || a.to - b.to);
  const items: FeedItem[] = [];
  let g = 0;
  for (let i = 0; i < visible.length; i += 1) {
    const ev = visible[i];
    if (ev === undefined) continue;
    while (g < sorted.length) {
      const gap = sorted[g];
      if (gap === undefined) break;
      if (gap.to > ev.t) break;
      if (gap.from < ev.t) items.push({ kind: "gap", gap });
      g += 1;
    }
    items.push({ kind: "event", ev });
  }
  return items;
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
    const capped = capFeed(filtered, cap);
    // FE-6: warn on fresh unknown families; the header count indicator and
    // the row ! UNKNOWN glyph below make them explicit, never OK.
    warnUnknown(filtered, props.machineId ?? "global");
    return { ...capped, summary: summarizeFeedAnomalies(filtered, capped.visible, capped.overflow) };
  }, [props.events, props.machineId, family, cap]);

  // FE-11 gap rows: markers for non-contiguous covered steps, interleaved
  // at the position where the missing steps would have rendered. The cap
  // and overflow badge still count events only.
  const items = useMemo(() => {
    if (props.steps === undefined) {
      return rows.visible.map((ev) => ({ kind: "event" as const, ev }));
    }
    return interleaveFeedGaps(rows.visible, findStepGaps(props.steps));
  }, [rows.visible, props.steps]);

  const testId =
    props.testId ?? (props.machineId === undefined ? "event-feed" : "machine-event-feed");

  return (
    <section data-testid={testId} aria-label={props.machineId ?? "global event feed"} className="sim-box px-panel scada-event-feed-panel">
      <h2 className="px-h2 panel-title">{props.machineId ? `Events: ${props.machineId}` : "Ch.07 Event Telemetry"}</h2>
      <div className="event-filter-bar">
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
            {/* FE-6: isolate unallowlisted rows as an explicit state. */}
            <option value={UNKNOWN_FAMILY}>{UNKNOWN_FAMILY}</option>
          </select>
        </label>
        {rows.overflow > 0 && (
          <span data-testid="feed-overflow">…+{rows.overflow} more</span>
        )}
        {rows.summary.unknownCount > 0 && (
          <span data-testid="feed-unknown">
            ! {rows.summary.unknownCount} unknown ({rows.summary.unknownNames.join(", ")})
          </span>
        )}
        {rows.summary.countMismatch && (
          <span data-testid="feed-mismatch">
            ! count mismatch: {rows.summary.visible}+{rows.summary.overflow} shown of {rows.summary.total}
          </span>
        )}
      </div>
      <div className="evt-feed-header">
        <span className="evt-th evt-col-step">STEP</span>
        <span className="evt-th evt-col-station">STATION</span>
        <span className="evt-th evt-col-event">EVENT</span>
        <span className="evt-th evt-col-kind">STATUS / CLASSIFICATION</span>
      </div>
      <ul
        className="evt-feed"
        data-testid="event-feed-list"
        style={{ flex: "1 1 auto", minHeight: 320, maxHeight: 380, overflowY: "auto" }}
      >
        {rows.visible.length === 0 && (
          <li data-testid="feed-empty" className="evt-empty-row">No events at this step yet.</li>
        )}
        {items.map((item, i) =>
          item.kind === "gap" ? (
            <FeedGapRow
              key={`gap-${item.gap.from}-${item.gap.to}-${i}`}
              gap={item.gap}
            />
          ) : (
            <FeedRow
              key={`${item.ev.t}-${item.ev.event}-${item.ev.machine}-${i}`}
              ev={item.ev}
            />
          ),
        )}
      </ul>
    </section>
  );
}

/**
 * FE-11 gap row: explicit discontinuity state. Dashed shape + ⚠ glyph +
 * "gap" wording carry the signal so color is never the only channel.
 * Static by construction (no animation; see feed-gaps.css).
 */
const FeedGapRow = memo(function FeedGapRow({
  gap,
}: {
  readonly gap: StepGap;
}): React.JSX.Element {
  const label = gapRangeLabel(gap);
  return (
    <li
      data-testid="feed-gap"
      data-gap-from={gap.from}
      data-gap-to={gap.to}
      className="feed-gap-row"
      role="note"
      aria-label={`gap in event steps: ${label} missing`}
    >
      <span className="evt-col-step">t={gap.from + 1}–{gap.to - 1}</span>
      <span className="evt-col-station">—</span>
      <span className="evt-col-event">
        <span className="feed-gap-glyph" aria-hidden="true">⚠</span>
        <span>gap</span>
      </span>
      <span className="evt-col-kind">{label} missing</span>
    </li>
  );
});

const FeedRow = memo(function FeedRow({ ev }: { readonly ev: TwinEvent }): React.JSX.Element {
  const kind = downKindOf(ev);
  // FE-6: familyOf never throws — unknown rows render as explicit UNKNOWN
  // (row class + ! glyph), never as OK. Warns land at the feed level.
  const familyAttr = familyOf(ev);
  const unknown = familyAttr === UNKNOWN_FAMILY;
  const rowClass = unknown
    ? "evt-row row-unknown"
    : kind === "injected"
      ? "evt-row row-down-injected"
      : kind === "natural"
        ? "evt-row row-down-natural"
        : "evt-row";
  return (
    <li
      data-testid="event-row"
      data-event={ev.event}
      data-machine={ev.machine}
      data-family={familyAttr}
      data-down-kind={kind ?? ""}
      className={rowClass}
    >
      <span className="evt-col-step">t={ev.t}</span>
      <span className="evt-col-station">{ev.machine}</span>
      <span className="evt-col-event">
        <span className={`evt-badge evt-badge-${familyAttr.toLowerCase()}`}>{ev.event}</span>
      </span>
      <span className="evt-col-kind">
        {unknown ? (
          <span className="row-kind row-kind-unknown" data-testid="event-unknown-glyph">
            ! UNKNOWN
          </span>
        ) : (
          kind !== null && (
            <span className="row-kind" data-testid="event-kind-glyph">
              ! {kind === "injected" ? "FAULT" : "NATURAL"}
            </span>
          )
        )}
        <span className="evt-raw-label" style={{ display: "none" }}>{labelFor(ev)}</span>
      </span>
    </li>
  );
});
