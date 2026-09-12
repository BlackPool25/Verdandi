// T8 SBUF/AGV legend. Hard MUST-NOT: never show an SBUF-divert legend
// for tails/feed/form — tails ride AGV, feed/form never divert.
import { AGV_STEPS, SBUF_CAP, SBUF_HIGH } from "./machineMeta";

const BOX: React.CSSProperties = {
  border: "1px solid #888",
  background: "#111",
  color: "#eee",
  padding: 8,
  fontSize: 16,
};

export function Legends(): React.JSX.Element {
  return (
    <section aria-label="sbuf agv legend" data-testid="sbuf-agv-legend" style={BOX}>
      <h2 className="px-h2">SBUF / AGV</h2>
      <p data-testid="legend-sbuf">
        SBUF cap {SBUF_CAP}; high-util badge at ≥{SBUF_HIGH} (80%).
      </p>
      <p data-testid="legend-tails">
        Tails A9/B9/C7 ride the AGV path (transit {AGV_STEPS[0]}–{AGV_STEPS[1]} steps) — never SBUF-divert.
      </p>
      <p data-testid="legend-feed-form">Feed/form machines never divert.</p>
    </section>
  );
}
