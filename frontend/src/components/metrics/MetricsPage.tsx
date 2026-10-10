import { useMemo } from "react";
import { useTwinStream } from "../../sim/TwinStreamProvider";
import { lineStatsFor, episodeStatsFor } from "../panels/selectors";
import { computeEpisodeAnomalies } from "../anomalies/anomalyAnalysis";

const LINE_A_IDS = ["A0", "A1", "A2", "A7", "A8", "A9"];
const LINE_B_IDS = ["B0", "B1", "B2", "B7P", "B7S", "B8", "B9"];
const LINE_C_IDS = ["C0", "C1", "C2", "C6", "C7"];
const ASSEMBLY_IDS = ["ASM0", "ASM1", "INSP0", "ASM2", "RWK0"];
const PACKAGING_IDS = ["PKG0", "PKG1", "PKG2"];

export function MetricsPage(): React.JSX.Element {
  const { source, episodeId } = useTwinStream();

  const line = source.panelTick ? lineStatsFor(source.panelTick) : null;
  const ep = episodeStatsFor(source.episodeHeader);
  const energy = source.energy;

  // Compute episode-wide statistics
  const summary = useMemo(
    () =>
      computeEpisodeAnomalies(
        source.rowCount,
        source.rowJson,
        (source.episodeHeader?.faults as readonly unknown[]) ?? [],
      ),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [source.rowCount, episodeId],
  );

  // Compute real line utilization percentages
  const lineMetrics = useMemo(() => {
    const calcLine = (ids: string[]) => {
      let run = 0;
      let starved = 0;
      let blocked = 0;
      let down = 0;
      const totalTicks = ids.length * Math.max(1, summary.totalSteps);

      for (const id of ids) {
        const mIdx = summary.machineList.indexOf(id);
        if (mIdx < 0) continue;
        const row = summary.stateMatrix[mIdx];
        if (!row) continue;
        for (const st of row) {
          if (st === "RUN") run++;
          else if (st === "STARVED") starved++;
          else if (st === "BLOCKED") blocked++;
          else if (st === "DOWN") down++;
        }
      }

      return {
        runPct: Number(((run / totalTicks) * 100).toFixed(1)),
        starvedPct: Number(((starved / totalTicks) * 100).toFixed(1)),
        blockedPct: Number(((blocked / totalTicks) * 100).toFixed(1)),
        downPct: Number(((down / totalTicks) * 100).toFixed(1)),
      };
    };

    return {
      lineA: calcLine(LINE_A_IDS),
      lineB: calcLine(LINE_B_IDS),
      lineC: calcLine(LINE_C_IDS),
      assembly: calcLine(ASSEMBLY_IDS),
      packaging: calcLine(PACKAGING_IDS),
    };
  }, [summary]);

  return (
    <div
      className="metrics-page-container font-pixel"
      data-testid="metrics-page"
      style={{
        padding: 16,
        height: "100%",
        overflowY: "auto",
        display: "flex",
        flexDirection: "column",
        gap: 16,
        boxSizing: "border-box",
      }}
    >
      <header
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          borderBottom: "2px solid var(--ink-900)",
          paddingBottom: 8,
          flexWrap: "wrap",
          gap: 8,
        }}
      >
        <div>
          <h2 className="px-h2" style={{ margin: 0, textTransform: "uppercase" }}>
            Plant Performance & Operational Metrics
          </h2>
          <p style={{ margin: "4px 0 0 0", color: "var(--text-muted)", fontSize: 13 }}>
            Continuous factory line throughput, honest utilization, yield distribution, and apparent energy analysis.
          </p>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <span className="px-badge" style={{ background: "var(--paper-100)", border: "2px solid var(--ink-900)" }}>
            EP: {episodeId?.slice(0, 8) ?? "none"}
          </span>
          <span className="px-badge" style={{ background: "var(--paper-100)", border: "2px solid var(--ink-900)" }}>
            STEP: {source.cursor} / 300
          </span>
          <span
            className="px-badge"
            style={{
              background: source.connected ? "var(--state-run)" : "var(--state-down)",
              color: "#fff",
              border: "2px solid var(--ink-900)",
            }}
          >
            {source.connected ? "CONNECTED" : "OFFLINE"}
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
          <div style={{ fontSize: 10, fontWeight: "bold", color: "var(--text-muted)" }}>
            LIVE PLANT THROUGHPUT
          </div>
          <div style={{ fontFamily: "var(--font-display, monospace)", fontSize: 20, marginTop: 6, color: "var(--state-run-ink)" }}>
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
          <div style={{ fontSize: 10, fontWeight: "bold", color: "var(--text-muted)" }}>
            TOTAL PRODUCTION YIELD (FINAL)
          </div>
          <div style={{ fontFamily: "var(--font-display, monospace)", fontSize: 20, marginTop: 6 }}>
            {ep.sunk ?? 0} <span style={{ fontSize: 12, fontFamily: "var(--font-ui)" }}>units shipped</span>
          </div>
          <div style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 4 }}>
            Scrapped: {ep.scrapped ?? 0} · Reworked: {ep.reworked ?? 0}
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
          <div style={{ fontSize: 10, fontWeight: "bold", color: "var(--text-muted)" }}>
            APPARENT ENERGY (CH9)
          </div>
          <div style={{ fontFamily: "var(--font-display, monospace)", fontSize: 20, marginTop: 6, color: "var(--series-sensor)" }}>
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
          <div style={{ fontSize: 10, fontWeight: "bold", color: "var(--text-muted)" }}>
            OVERFLOW STORAGE (SBUF)
          </div>
          <div
            style={{
              fontFamily: "var(--font-display, monospace)",
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
            Peak Occupancy: {ep.sbufMax ?? "—"} / 30 units
          </div>
        </div>
      </div>

      {/* Production Line Breakdown - REAL DATA ONLY */}
      <section
        className="sim-box"
        style={{
          background: "var(--paper-100)",
          border: "2px solid var(--ink-900)",
          padding: 16,
          boxShadow: "var(--shadow-card)",
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
          <h3 className="px-h3" style={{ margin: 0 }}>
            Production Line Balancing & Active Utilization
          </h3>
          <span style={{ fontSize: 11, color: "var(--text-muted)" }}>
            Calculated across {summary.totalSteps} steps from live stream rows
          </span>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          {/* Line A */}
          <div>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, fontWeight: "bold" }}>
              <span>LINE A: Machining & Precision Milling (A0 - A9)</span>
              <span>{lineMetrics.lineA.runPct}% RUN · {lineMetrics.lineA.starvedPct}% WAITING · {lineMetrics.lineA.downPct}% DOWN</span>
            </div>
            <div style={{ height: 12, background: "var(--paper-300)", border: "1px solid var(--ink-900)", marginTop: 4, display: "flex" }}>
              <div style={{ height: "100%", width: `${lineMetrics.lineA.runPct}%`, background: "var(--state-run)" }} title={`RUN: ${lineMetrics.lineA.runPct}%`} />
              <div style={{ height: "100%", width: `${lineMetrics.lineA.starvedPct}%`, background: "var(--state-starved)" }} title={`STARVED: ${lineMetrics.lineA.starvedPct}%`} />
              <div style={{ height: "100%", width: `${lineMetrics.lineA.downPct}%`, background: "var(--state-down)" }} title={`DOWN: ${lineMetrics.lineA.downPct}%`} />
            </div>
          </div>

          {/* Line B */}
          <div>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, fontWeight: "bold" }}>
              <span>LINE B: Process & Heat Treatment (B0 - B9)</span>
              <span>{lineMetrics.lineB.runPct}% RUN · {lineMetrics.lineB.starvedPct}% WAITING · {lineMetrics.lineB.downPct}% DOWN</span>
            </div>
            <div style={{ height: 12, background: "var(--paper-300)", border: "1px solid var(--ink-900)", marginTop: 4, display: "flex" }}>
              <div style={{ height: "100%", width: `${lineMetrics.lineB.runPct}%`, background: "var(--state-run)" }} title={`RUN: ${lineMetrics.lineB.runPct}%`} />
              <div style={{ height: "100%", width: `${lineMetrics.lineB.starvedPct}%`, background: "var(--state-starved)" }} title={`STARVED: ${lineMetrics.lineB.starvedPct}%`} />
              <div style={{ height: "100%", width: `${lineMetrics.lineB.downPct}%`, background: "var(--state-down)" }} title={`DOWN: ${lineMetrics.lineB.downPct}%`} />
            </div>
          </div>

          {/* Line C */}
          <div>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, fontWeight: "bold" }}>
              <span>LINE C: Secondary Stamping & Coating (C0 - C7)</span>
              <span>{lineMetrics.lineC.runPct}% RUN · {lineMetrics.lineC.starvedPct}% WAITING · {lineMetrics.lineC.downPct}% DOWN</span>
            </div>
            <div style={{ height: 12, background: "var(--paper-300)", border: "1px solid var(--ink-900)", marginTop: 4, display: "flex" }}>
              <div style={{ height: "100%", width: `${lineMetrics.lineC.runPct}%`, background: "var(--state-run)" }} title={`RUN: ${lineMetrics.lineC.runPct}%`} />
              <div style={{ height: "100%", width: `${lineMetrics.lineC.starvedPct}%`, background: "var(--state-starved)" }} title={`STARVED: ${lineMetrics.lineC.starvedPct}%`} />
              <div style={{ height: "100%", width: `${lineMetrics.lineC.downPct}%`, background: "var(--state-down)" }} title={`DOWN: ${lineMetrics.lineC.downPct}%`} />
            </div>
          </div>

          {/* Assembly Cell */}
          <div>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, fontWeight: "bold" }}>
              <span>ASSEMBLY & REWORK CELL (ASM0 - ASM2, INSP0, RWK0)</span>
              <span>{lineMetrics.assembly.runPct}% RUN · {lineMetrics.assembly.starvedPct}% WAITING · {lineMetrics.assembly.downPct}% DOWN</span>
            </div>
            <div style={{ height: 12, background: "var(--paper-300)", border: "1px solid var(--ink-900)", marginTop: 4, display: "flex" }}>
              <div style={{ height: "100%", width: `${lineMetrics.assembly.runPct}%`, background: "var(--state-run)" }} title={`RUN: ${lineMetrics.assembly.runPct}%`} />
              <div style={{ height: "100%", width: `${lineMetrics.assembly.starvedPct}%`, background: "var(--state-starved)" }} title={`STARVED: ${lineMetrics.assembly.starvedPct}%`} />
              <div style={{ height: "100%", width: `${lineMetrics.assembly.downPct}%`, background: "var(--state-down)" }} title={`DOWN: ${lineMetrics.assembly.downPct}%`} />
            </div>
          </div>

          {/* Packaging */}
          <div>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, fontWeight: "bold" }}>
              <span>PACKAGING & OUTBOUND SINKS (PKG0 - PKG2)</span>
              <span>{lineMetrics.packaging.runPct}% RUN · {lineMetrics.packaging.starvedPct}% WAITING · {lineMetrics.packaging.downPct}% DOWN</span>
            </div>
            <div style={{ height: 12, background: "var(--paper-300)", border: "1px solid var(--ink-900)", marginTop: 4, display: "flex" }}>
              <div style={{ height: "100%", width: `${lineMetrics.packaging.runPct}%`, background: "var(--state-run)" }} title={`RUN: ${lineMetrics.packaging.runPct}%`} />
              <div style={{ height: "100%", width: `${lineMetrics.packaging.starvedPct}%`, background: "var(--state-starved)" }} title={`STARVED: ${lineMetrics.packaging.starvedPct}%`} />
              <div style={{ height: "100%", width: `${lineMetrics.packaging.downPct}%`, background: "var(--state-down)" }} title={`DOWN: ${lineMetrics.packaging.downPct}%`} />
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
