// T8 buffer bars: level/cap per buffer, SBUF high-util≥80% badge.
// Tails show the AGV path note here too; SBUF-divert is never claimed
// for tails/feed/form (see Legends + tailPathFor).
import { bufferBarsFor, type PanelTick } from "./selectors";

export function BufferBars(props: { readonly tick: PanelTick | null }): React.JSX.Element {
  const { tick } = props;
  if (tick === null) {
    return (
      <section aria-label="buffer bars" data-testid="buffer-bars" className="sim-box px-panel buffer-matrix-panel">
        <h2 className="px-h2 panel-title">Plant Buffers (31 Cells)</h2>
        <p data-testid="buffer-bars-empty" className="empty-selection-note">No tick yet.</p>
      </section>
    );
  }
  const bars = bufferBarsFor(tick);
  return (
    <section
      aria-label="buffer bars"
      data-testid="buffer-bars"
      className="sim-box px-panel buffer-matrix-panel"
      style={{ maxWidth: "100%", overflowX: "auto" }}
    >
      <div className="buffer-matrix-header">
        <h2 className="px-h2 panel-title">Plant Buffers (31 Storage Cells)</h2>
        <span className="buffer-matrix-legend">Nominal capacity: 10–30 units</span>
      </div>
      <ul
        className="buffer-matrix-grid"
        style={{
          listStyle: "none",
          margin: 0,
          padding: 0,
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(130px, 1fr))",
          gap: "6px 10px",
          maxWidth: "100%",
        }}
      >
        {bars.map((b) => (
          <li
            key={b.id}
            data-testid={`buffer-bar-${b.id}`}
            data-high={b.high ? "true" : "false"}
            className={`buffer-cell ${b.high ? "is-high-util" : ""}`}
            style={{
              overflowWrap: "anywhere",
              background: b.high ? "var(--vd-state-starved-bg)" : "var(--vd-surface-raised)",
              border: b.high ? "1px solid var(--vd-alarm-alert)" : "1px solid var(--vd-border-muted)",
              boxShadow: "inset 1px 1px 0 var(--vd-border-highlight), inset -1px -1px 0 var(--vd-border-shadow)",
              padding: "4px 6px",
            }}
          >
            <div className="buffer-cell__meta" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 3 }}>
              <span data-testid={`buffer-level-${b.id}`} style={{ fontFamily: "var(--font-data)", fontSize: 11, fontWeight: 700 }}>
                {b.id}: {b.level}/{b.cap}
              </span>
              {b.high && (
                <strong data-testid="sbuf-high-badge" style={{ fontFamily: "var(--font-display)", fontSize: 7, color: "var(--vd-state-down)" }}>
                  HIGH ≥80%
                </strong>
              )}
            </div>
            <div
              data-testid={`buffer-track-${b.id}`}
              aria-hidden="true"
              style={{
                height: 8,
                background: "var(--vd-surface-sunken)",
                border: "1px solid var(--vd-border-dark)",
                position: "relative",
                overflow: "hidden",
                maxWidth: "100%",
              }}
            >
              <div
                data-testid={`buffer-fill-${b.id}`}
                style={{
                  height: "100%",
                  width: `${Math.min(100, Math.max(0, b.util * 100))}%`,
                  background: b.high ? "var(--vd-alarm-alert)" : "var(--vd-state-run)",
                }}
              />
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
