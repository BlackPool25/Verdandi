// T8 SBUF/AGV legend. Hard MUST-NOT: never show an SBUF-divert legend
// for tails/feed/form — tails ride AGV, feed/form never divert.
import { AGV_STEPS, SBUF_CAP, SBUF_HIGH } from "./machineMeta";

export function Legends(): React.JSX.Element {
  return (
    <section aria-label="sbuf agv legend" data-testid="sbuf-agv-legend" className="sim-box px-panel scada-legend-panel">
      <h2 className="px-h2 panel-title">SCADA Process & Logistics Rules</h2>

      {/* SBUF and Logistics (Preserves existing testids) */}
      <div style={{ display: "flex", flexDirection: "column", gap: 3, marginBottom: 8, paddingBottom: 6, borderBottom: "1px solid var(--vd-border-muted)" }}>
        <div style={{ fontSize: 10, fontFamily: "var(--font-display)", color: "var(--ink-950)", textTransform: "uppercase" }}>
          Logistics Corridor & SBUF
        </div>
        <p data-testid="legend-sbuf" style={{ margin: 0, fontSize: 13 }}>
          SBUF capacity {SBUF_CAP} units; high-utilization alarm badge triggers at ≥{SBUF_HIGH} (80%).
        </p>
        <p data-testid="legend-tails" style={{ margin: 0, fontSize: 13 }}>
          Tails A9/B9/C7 ride the AGV fleet corridor (transit {AGV_STEPS[0]}–{AGV_STEPS[1]} steps) — never SBUF-divert.
        </p>
        <p data-testid="legend-feed-form" style={{ margin: 0, fontSize: 13 }}>
          Feed and form machines never divert to overflow storage.
        </p>
      </div>

      {/* ISA-101 Operational States */}
      <div style={{ display: "flex", flexDirection: "column", gap: 4, marginBottom: 8, paddingBottom: 6, borderBottom: "1px solid var(--vd-border-muted)" }}>
        <div style={{ fontSize: 10, fontFamily: "var(--font-display)", color: "var(--ink-950)", textTransform: "uppercase" }}>
          Machine Operational States
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 4, fontSize: 12 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <span style={{ display: "inline-block", width: 10, height: 10, background: "var(--state-run)", border: "1px solid #141b26" }} />
            <span><strong>RUN</strong>: Processing parts</span>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <span style={{ display: "inline-block", width: 10, height: 10, background: "var(--state-starved)", border: "1px solid #141b26" }} />
            <span><strong>STARVED</strong>: Waiting for parts</span>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <span style={{ display: "inline-block", width: 10, height: 10, background: "var(--state-blocked)", border: "1px solid #141b26" }} />
            <span><strong>BLOCKED</strong>: Buffer is full</span>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <span style={{ display: "inline-block", width: 10, height: 10, background: "var(--state-down)", border: "1px solid #141b26" }} />
            <span><strong>DOWN</strong>: Mechanical stoppage</span>
          </div>
        </div>
      </div>

      {/* Process Mechanics & Failure Independence */}
      <div style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 12, color: "var(--text-main)" }}>
        <div style={{ fontSize: 10, fontFamily: "var(--font-display)", color: "var(--ink-950)", textTransform: "uppercase" }}>
          Failure Independence & Flow Propagation
        </div>
        <p style={{ margin: 0, lineHeight: 1.35 }}>
          <strong>No Cascading Breakdowns</strong>: Stations break down independently per Poisson MTTF wear. An upstream stoppage does <em>not</em> trigger secondary mechanical breakdowns downstream.
        </p>
        <p style={{ margin: 0, lineHeight: 1.35 }}>
          <strong>Material Starvation</strong>: Upstream breakdowns starve downstream machines of material (they turn blue/STARVED).
        </p>
        <p style={{ margin: 0, lineHeight: 1.35 }}>
          <strong>Buffer Congestion</strong>: Downstream stoppages back up intermediate storage cells and block upstream stations (they turn amber/BLOCKED).
        </p>
      </div>
    </section>
  );
}
