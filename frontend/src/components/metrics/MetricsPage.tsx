import { useTwinStream } from "../../sim/TwinStreamProvider";
import { lineStatsFor, episodeStatsFor } from "../panels/selectors";

export function MetricsPage(): React.JSX.Element {
  const { source, episodeId } = useTwinStream();

  const line = source.panelTick ? lineStatsFor(source.panelTick) : null;
  const ep = episodeStatsFor(source.episodeHeader);
  const energy = source.energy;

  return (
    <div
      className="metrics-page-container"
      data-testid="metrics-page"
      style={{
        padding: 16,
        height: "100%",
        overflowY: "auto",
        display: "flex",
        flexDirection: "column",
        gap: 16,
      }}
    >
      <header
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          borderBottom: "2px solid var(--ink-900)",
          paddingBottom: 8,
        }}
      >
        <div>
          <h2 className="px-h2" style={{ margin: 0, textTransform: "uppercase" }}>
            Plant Performance & Operational Metrics
          </h2>
          <p style={{ margin: "4px 0 0 0", color: "var(--text-muted)", fontSize: 13 }}>
            Continuous factory line throughput, yield distribution, buffer saturation, and apparent energy analysis.
          </p>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <span className="px-badge" style={{ background: "var(--paper-100)", border: "2px solid var(--ink-900)" }}>
            Ep: {episodeId?.slice(0, 8) ?? "none"}
          </span>
          <span className="px-badge" style={{ background: "var(--paper-100)", border: "2px solid var(--ink-900)" }}>
            Step: {source.cursor} / 300
          </span>
        </div>
      </header>

      {/* Aggregate KPI Cards */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
          gap: 12,
        }}
      >
        <div
          className="sim-box"
          style={{
            background: "var(--paper-100)",
            border: "2px solid var(--ink-900)",
            padding: 12,
            boxShadow: "var(--shadow-card)",
          }}
        >
          <div style={{ fontSize: 11, fontWeight: "bold", color: "var(--text-muted)" }}>
            LIVE PLANT THROUGHPUT
          </div>
          <div style={{ fontFamily: "var(--font-display)", fontSize: 20, marginTop: 6, color: "var(--state-run-ink)" }}>
            {line?.tputSum ?? 0} <span style={{ fontSize: 12, fontFamily: "var(--font-ui)" }}>parts/tick</span>
          </div>
          <div style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 4 }}>
            Active Machines: {line?.run ?? 0}/26
          </div>
        </div>

        <div
          className="sim-box"
          style={{
            background: "var(--paper-100)",
            border: "2px solid var(--ink-900)",
            padding: 12,
            boxShadow: "var(--shadow-card)",
          }}
        >
          <div style={{ fontSize: 11, fontWeight: "bold", color: "var(--text-muted)" }}>
            TOTAL PRODUCTION YIELD (FINAL)
          </div>
          <div style={{ fontFamily: "var(--font-display)", fontSize: 20, marginTop: 6 }}>
            {ep.sunk ?? 0} <span style={{ fontSize: 12, fontFamily: "var(--font-ui)" }}>units shipped</span>
          </div>
          <div style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 4 }}>
            Scrapped: {ep.scrapped ?? 0} | Reworked: {ep.reworked ?? 0}
          </div>
        </div>

        <div
          className="sim-box"
          style={{
            background: "var(--paper-100)",
            border: "2px solid var(--ink-900)",
            padding: 12,
            boxShadow: "var(--shadow-card)",
          }}
        >
          <div style={{ fontSize: 11, fontWeight: "bold", color: "var(--text-muted)" }}>
            APPARENT ENERGY (CH9)
          </div>
          <div style={{ fontFamily: "var(--font-display)", fontSize: 20, marginTop: 6, color: "var(--series-sensor)" }}>
            {energy?.sumKVAh ? energy.sumKVAh.toFixed(1) : "—"}{" "}
            <span style={{ fontSize: 12, fontFamily: "var(--font-ui)" }}>kVAh</span>
          </div>
          <div style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 4 }}>
            Intensity: {energy?.perUnit ? energy.perUnit.toFixed(1) : "—"} kVAh/unit
          </div>
        </div>

        <div
          className="sim-box"
          style={{
            background: "var(--paper-100)",
            border: "2px solid var(--ink-900)",
            padding: 12,
            boxShadow: "var(--shadow-card)",
          }}
        >
          <div style={{ fontSize: 11, fontWeight: "bold", color: "var(--text-muted)" }}>
            OVERFLOW STORAGE (SBUF)
          </div>
          <div
            style={{
              fontFamily: "var(--font-display)",
              fontSize: 20,
              marginTop: 6,
              color: line?.sbufHigh ? "var(--state-down-ink)" : "var(--text-main)",
            }}
          >
            {line?.sbufLevel ?? 0} / 30{" "}
            <span style={{ fontSize: 12, fontFamily: "var(--font-ui)" }}>
              {line?.sbufHigh ? "HIGH (≥80%)" : "NOMINAL"}
            </span>
          </div>
          <div style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 4 }}>
            AGV corridor drain capacity
          </div>
        </div>
      </div>

      {/* Production Line Breakdown */}
      <section
        className="sim-box"
        style={{
          background: "var(--paper-100)",
          border: "2px solid var(--ink-900)",
          padding: 16,
          boxShadow: "var(--shadow-card)",
        }}
      >
        <h3 className="px-h3" style={{ margin: "0 0 12px 0" }}>
          Production Lines & Balancing Overview
        </h3>
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <div>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13, fontWeight: "bold" }}>
              <span>LINE A: Machining & Precision Milling (A0 - A9)</span>
              <span>6 Stations · Nominal Takt 5.0s</span>
            </div>
            <div style={{ height: 10, background: "var(--paper-300)", border: "1px solid var(--ink-900)", marginTop: 4 }}>
              <div style={{ height: "100%", width: "85%", background: "var(--state-run)" }} />
            </div>
          </div>

          <div>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13, fontWeight: "bold" }}>
              <span>LINE B: Process & Heat Treatment (B0 - B9)</span>
              <span>7 Stations · Primary B7P / Spare B7S</span>
            </div>
            <div style={{ height: 10, background: "var(--paper-300)", border: "1px solid var(--ink-900)", marginTop: 4 }}>
              <div style={{ height: "100%", width: "70%", background: "var(--state-blocked)" }} />
            </div>
          </div>

          <div>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13, fontWeight: "bold" }}>
              <span>LINE C: Secondary Stamping & Coating (C0 - C7)</span>
              <span>5 Stations · Powder Coating & Audit Tail</span>
            </div>
            <div style={{ height: 10, background: "var(--paper-300)", border: "1px solid var(--ink-900)", marginTop: 4 }}>
              <div style={{ height: "100%", width: "95%", background: "var(--state-run)" }} />
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
