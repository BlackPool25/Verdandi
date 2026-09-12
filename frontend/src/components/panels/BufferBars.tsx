// T8 buffer bars: level/cap per buffer, SBUF high-util≥80% badge.
// Tails show the AGV path note here too; SBUF-divert is never claimed
// for tails/feed/form (see Legends + tailPathFor).
import { bufferBarsFor, type PanelTick } from "./selectors";

const BOX: React.CSSProperties = {
  border: "1px solid #888",
  background: "#111",
  color: "#eee",
  padding: 8,
  fontSize: 16,
};

export function BufferBars(props: { readonly tick: PanelTick | null }): React.JSX.Element {
  const { tick } = props;
  if (tick === null) {
    return (
      <section aria-label="buffer bars" data-testid="buffer-bars" style={BOX}>
        <h2 className="px-h2">Buffers</h2>
        <p data-testid="buffer-bars-empty">No tick yet.</p>
      </section>
    );
  }
  const bars = bufferBarsFor(tick);
  return (
    <section aria-label="buffer bars" data-testid="buffer-bars" style={BOX}>
      <h2 className="px-h2">Buffers</h2>
      <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
        {bars.map((b) => (
          <li key={b.id} data-testid={`buffer-bar-${b.id}`}>
            <span data-testid={`buffer-level-${b.id}`}>
              {b.id}: {b.level}/{b.cap}
            </span>{" "}
            {b.high && (
              <strong data-testid="sbuf-high-badge">HIGH-UTIL ≥80%</strong>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
