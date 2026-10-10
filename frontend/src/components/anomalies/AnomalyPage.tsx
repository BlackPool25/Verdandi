import { useMemo, useState } from "react";
import { useTwinStream } from "../../sim/TwinStreamProvider";
import { computeEpisodeAnomalies } from "./anomalyAnalysis";
import { AnomalyHeatmap } from "./AnomalyHeatmap";
import type { FaultDraft } from "../controls/types";

interface DemoPreset {
  readonly id: string;
  readonly title: string;
  readonly badge: string;
  readonly description: string;
  readonly seed: number;
  readonly faults: readonly FaultDraft[];
}

const DEMO_PRESETS: readonly DemoPreset[] = [
  {
    id: "baseline",
    title: "1. Baseline (Natural Wear Only)",
    badge: "NOMINAL",
    description: "Seed 777 nominal run: zero synthetic faults, natural Poisson MTTF mechanical wear only.",
    seed: 777,
    faults: [],
  },
  {
    id: "sensor-drift-bias",
    title: "2. Sensor Drift & Bias Storm",
    badge: "SENSOR FAULTS",
    description: "Injected calibration drift on A2 (t=130) and DC offset bias on B1 (t=165).",
    seed: 777,
    faults: [
      { id: "f-drift-a2", faultClass: "drift", origin: "A2", t0: 130, dur: 25, extra: {} },
      { id: "f-bias-b1", faultClass: "bias", origin: "B1", t0: 165, dur: 20, extra: {} },
    ],
  },
  {
    id: "quality-rework",
    title: "3. Quality Defect & Rework Loop",
    badge: "QUALITY REJECTS",
    description: "Assembly tolerance failure on ASM2 (t=140), triggering defect diversion to RWK0 Rework Bay.",
    seed: 777,
    faults: [
      { id: "f-quality-asm2", faultClass: "quality", origin: "ASM2", t0: 140, dur: 25, extra: {} },
    ],
  },
  {
    id: "multi-fault-storm",
    title: "4. Multi-Anomaly Industrial Storm",
    badge: "5 FAULT CLASSES",
    description: "Composite scenario: Sensor Drift (A2), Sensor Bias (B1), Cycle Delay (C2), Quality (ASM2), Stoppage (C6).",
    seed: 777,
    faults: [
      { id: "f-drift-a2", faultClass: "drift", origin: "A2", t0: 130, dur: 25, extra: {} },
      { id: "f-bias-b1", faultClass: "bias", origin: "B1", t0: 165, dur: 20, extra: {} },
      { id: "f-delay-c2", faultClass: "delay", origin: "C2", t0: 195, dur: 22, extra: {} },
      { id: "f-quality-asm2", faultClass: "quality", origin: "ASM2", t0: 225, dur: 25, extra: {} },
      { id: "f-down-c6", faultClass: "breakdown", origin: "C6", t0: 260, dur: 20, extra: {} },
    ],
  },
];

export function AnomalyPage(): React.JSX.Element {
  const { source, episodeId, selectedId, setSelectedId, startNewEpisode } = useTwinStream();
  const [selectedCategory, setSelectedCategory] = useState<string>("ALL");
  const [isLaunchingPreset, setIsLaunchingPreset] = useState<boolean>(false);

  // Compute episode-wide anomaly matrix and statistics across all buffered steps
  const summary = useMemo(
    () =>
      computeEpisodeAnomalies(
        source.rowCount,
        source.rowJson,
        (source.episodeHeader?.faults as readonly unknown[]) ?? [],
      ),
    // Recompute when rowCount or episodeId changes
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [source.rowCount, episodeId, source.episodeHeader?.faults],
  );

  const cursor = Math.max(0, source.cursor);

  const handleLaunchPreset = async (preset: DemoPreset) => {
    setIsLaunchingPreset(true);
    try {
      await startNewEpisode(preset.seed, [...preset.faults], true);
    } catch (err) {
      console.error("Failed to launch demonstration preset:", err);
    } finally {
      setIsLaunchingPreset(false);
    }
  };

  const filteredIncidents = useMemo(() => {
    if (selectedCategory === "ALL") return summary.incidents;
    if (selectedCategory === "MECHANICAL")
      return summary.incidents.filter((i) => i.category === "mechanical");
    if (selectedCategory === "INJECTED")
      return summary.incidents.filter((i) => i.type === "injected");
    if (selectedCategory === "LOGISTICS")
      return summary.incidents.filter((i) => i.category === "logistics_wait");
    if (selectedCategory === "QUALITY")
      return summary.incidents.filter((i) => i.category === "quality_defect");
    if (selectedCategory === "SENSOR")
      return summary.incidents.filter((i) => i.category === "sensor_drift" || i.category === "sensor_bias");
    if (selectedCategory === "PROCESS")
      return summary.incidents.filter((i) => i.category === "process_delay" || i.category === "material_loss");
    return summary.incidents;
  }, [summary.incidents, selectedCategory]);

  return (
    <div
      className="anomaly-page-container font-pixel"
      data-testid="anomaly-page"
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
      {/* Top Header */}
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
            Plant Operational State & Incident Diagnostics
          </h2>
          <p style={{ margin: "4px 0 0 0", color: "var(--text-muted)", fontSize: 13 }}>
            Multi-station 26-machine operational heatmap, failure independence verification, and breakdown telemetry.
          </p>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <span className="px-badge" style={{ background: "var(--paper-100)", border: "2px solid var(--ink-900)" }}>
            EP: {episodeId?.slice(0, 8) ?? "none"}
          </span>
          <span className="px-badge" style={{ background: "var(--paper-100)", border: "2px solid var(--ink-900)" }}>
            STEP: {cursor} / 300
          </span>
          <span
            className="px-badge"
            style={{
              background: source.connected ? "var(--state-run)" : "var(--state-down)",
              color: "#fff",
              border: "2px solid var(--ink-900)",
            }}
          >
            {source.connected ? "LIVE STREAM" : "OFFLINE"}
          </span>
        </div>
      </header>

      {/* 1-Click Anomaly Demonstration Presets */}
      <section
        className="sim-box"
        style={{
          background: "var(--paper-100)",
          border: "2px solid var(--ink-900)",
          padding: 12,
          boxShadow: "var(--shadow-card)",
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8, flexWrap: "wrap", gap: 6 }}>
          <div>
            <h3 className="px-h3" style={{ margin: 0, fontSize: 13 }}>
              Demonstration Scenarios (Explore All Fault Types)
            </h3>
            <p style={{ margin: "2px 0 0 0", fontSize: 11, color: "var(--text-muted)" }}>
              Switch simulation scenarios to inject and observe different anomaly classes across the digital twin.
            </p>
          </div>
          {isLaunchingPreset && (
            <span className="px-badge" style={{ background: "var(--state-blocked)", color: "#141b26", fontSize: 10 }}>
              REPLAYING NEW SCENARIO...
            </span>
          )}
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: 8 }}>
          {DEMO_PRESETS.map((p) => {
            const isActive =
              p.id === "baseline"
                ? summary.injectedFaultCount === 0
                : summary.injectedFaultCount === p.faults.length;
            return (
              <div
                key={p.id}
                style={{
                  background: isActive ? "var(--paper-50)" : "var(--paper-200)",
                  border: isActive ? "2px solid var(--ink-950)" : "1px solid var(--ink-500)",
                  padding: 8,
                  display: "flex",
                  flexDirection: "column",
                  justifyContent: "space-between",
                  gap: 6,
                }}
              >
                <div>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <span style={{ fontWeight: "bold", fontSize: 11 }}>{p.title}</span>
                    <span
                      className="px-badge"
                      style={{
                        fontSize: 9,
                        padding: "1px 4px",
                        background: isActive ? "var(--state-run)" : "var(--paper-300)",
                        color: isActive ? "#fff" : "var(--ink-950)",
                      }}
                    >
                      {p.badge}
                    </span>
                  </div>
                  <p style={{ margin: "4px 0 0 0", fontSize: 10, color: "var(--text-muted)", lineHeight: 1.3 }}>
                    {p.description}
                  </p>
                </div>
                <button
                  type="button"
                  className="px-btn"
                  disabled={isLaunchingPreset}
                  onClick={() => handleLaunchPreset(p)}
                  style={{
                    fontSize: 10,
                    padding: "3px 6px",
                    width: "100%",
                    cursor: isLaunchingPreset ? "wait" : "pointer",
                    background: isActive ? "var(--paper-100)" : undefined,
                  }}
                >
                  {isActive ? "✓ ACTIVE SCENARIO" : "▶ LOAD SCENARIO"}
                </button>
              </div>
            );
          })}
        </div>
      </section>

      {/* KPI Horizon Summary Strip */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))",
          gap: 10,
        }}
      >
        {/* Mechanical Wear */}
        <div
          className="sim-box"
          style={{
            background: "var(--paper-100)",
            border: "2px solid var(--ink-900)",
            padding: 10,
            boxShadow: "var(--shadow-card)",
          }}
        >
          <div style={{ fontSize: 9, color: "var(--text-muted)", textTransform: "uppercase" }}>
            MECHANICAL WEAR
          </div>
          <div
            style={{
              fontFamily: "var(--font-display, monospace)",
              fontSize: 20,
              marginTop: 4,
              color: summary.naturalBreakdownCount > 0 ? "var(--series-sensor)" : "var(--state-run-ink)",
            }}
          >
            {summary.naturalBreakdownCount}
          </div>
          <div style={{ fontSize: 10, color: "var(--text-muted)", marginTop: 2 }}>
            {summary.downTicks} ticks down · Poisson MTTF
          </div>
        </div>

        {/* Injected Faults */}
        <div
          className="sim-box"
          style={{
            background: "var(--paper-100)",
            border: "2px solid var(--ink-900)",
            padding: 10,
            boxShadow: "var(--shadow-card)",
          }}
        >
          <div style={{ fontSize: 9, color: "var(--text-muted)", textTransform: "uppercase" }}>
            INJECTED FAULTS
          </div>
          <div
            style={{
              fontFamily: "var(--font-display, monospace)",
              fontSize: 20,
              marginTop: 4,
              color: summary.injectedFaultCount > 0 ? "var(--state-down-ink)" : "var(--state-run-ink)",
            }}
          >
            {summary.injectedFaultCount}
          </div>
          <div style={{ fontSize: 10, color: "var(--text-muted)", marginTop: 2 }}>
            {summary.injectedFaultCount > 0 ? "Synthetic faults active" : "0 faults (Nominal)"}
          </div>
        </div>

        {/* Quality Defects & Rework */}
        <div
          className="sim-box"
          style={{
            background: "var(--paper-100)",
            border: "2px solid var(--ink-900)",
            padding: 10,
            boxShadow: "var(--shadow-card)",
          }}
        >
          <div style={{ fontSize: 9, color: "var(--text-muted)", textTransform: "uppercase" }}>
            QUALITY & REWORK
          </div>
          <div
            style={{
              fontFamily: "var(--font-display, monospace)",
              fontSize: 20,
              marginTop: 4,
              color: summary.qualityDefectCount > 0 ? "var(--state-blocked-ink)" : "var(--state-run-ink)",
            }}
          >
            {summary.qualityDefectCount}
          </div>
          <div style={{ fontSize: 10, color: "var(--text-muted)", marginTop: 2 }}>
            Inspection & rework loops
          </div>
        </div>

        {/* Logistics AGV Waits */}
        <div
          className="sim-box"
          style={{
            background: "var(--paper-100)",
            border: "2px solid var(--ink-900)",
            padding: 10,
            boxShadow: "var(--shadow-card)",
          }}
        >
          <div style={{ fontSize: 9, color: "var(--text-muted)", textTransform: "uppercase" }}>
            LOGISTICS AGV WAITS
          </div>
          <div
            style={{
              fontFamily: "var(--font-display, monospace)",
              fontSize: 20,
              marginTop: 4,
              color: summary.logisticsWaitCount > 0 ? "var(--state-starved-ink, #0072b2)" : "var(--state-run-ink)",
            }}
          >
            {summary.logisticsWaitCount}
          </div>
          <div style={{ fontSize: 10, color: "var(--text-muted)", marginTop: 2 }}>
            Aisle corridor transfers
          </div>
        </div>

        {/* Statistical Sensor Outliers */}
        <div
          className="sim-box"
          style={{
            background: "var(--paper-100)",
            border: "2px solid var(--ink-900)",
            padding: 10,
            boxShadow: "var(--shadow-card)",
          }}
        >
          <div style={{ fontSize: 9, color: "var(--text-muted)", textTransform: "uppercase" }}>
            SENSOR OUTLIERS (&gt;3σ)
          </div>
          <div
            style={{
              fontFamily: "var(--font-display, monospace)",
              fontSize: 20,
              marginTop: 4,
              color: summary.sensorAnomalyCount > 0 ? "var(--state-down-ink)" : "var(--state-run-ink)",
            }}
          >
            {summary.sensorAnomalyCount}
          </div>
          <div style={{ fontSize: 10, color: "var(--text-muted)", marginTop: 2 }}>
            Continuous telemetry anomalies
          </div>
        </div>

        {/* Material Starvation */}
        <div
          className="sim-box"
          style={{
            background: "var(--paper-100)",
            border: "2px solid var(--ink-900)",
            padding: 10,
            boxShadow: "var(--shadow-card)",
          }}
        >
          <div style={{ fontSize: 9, color: "var(--text-muted)", textTransform: "uppercase" }}>
            MATERIAL STARVATION
          </div>
          <div
            style={{
              fontFamily: "var(--font-display, monospace)",
              fontSize: 20,
              marginTop: 4,
              color: "var(--state-starved-ink, #0072b2)",
            }}
          >
            {summary.starvedRatePct.toFixed(2)}%
          </div>
          <div style={{ fontSize: 10, color: "var(--text-muted)", marginTop: 2 }}>
            {summary.starvedTicks} ticks waiting for parts
          </div>
        </div>

        {/* Plant Availability */}
        <div
          className="sim-box"
          style={{
            background: "var(--paper-100)",
            border: "2px solid var(--ink-900)",
            padding: 10,
            boxShadow: "var(--shadow-card)",
          }}
        >
          <div style={{ fontSize: 9, color: "var(--text-muted)", textTransform: "uppercase" }}>
            PLANT AVAILABILITY
          </div>
          <div
            style={{
              fontFamily: "var(--font-display, monospace)",
              fontSize: 20,
              marginTop: 4,
              color: "var(--state-run-ink)",
            }}
          >
            {summary.availabilityPct.toFixed(2)}%
          </div>
          <div style={{ fontSize: 10, color: "var(--text-muted)", marginTop: 2 }}>
            {summary.runTicks} ticks nominal RUN
          </div>
        </div>
      </div>

      {/* Educational Banner: Independent Failure Model & Material Flow Propagation */}
      <section
        className="sim-box"
        style={{
          background: "var(--paper-50)",
          border: "2px solid var(--ink-900)",
          borderLeft: "6px solid var(--state-starved)",
          padding: "10px 14px",
          boxShadow: "var(--shadow-card)",
          display: "flex",
          flexDirection: "column",
          gap: 4,
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            fontFamily: "var(--font-display, monospace)",
            fontSize: 11,
            color: "var(--ink-950)",
            textTransform: "uppercase",
          }}
        >
          <span style={{ color: "var(--state-starved)" }}>ℹ</span> PROCESS PRINCIPLE: INDEPENDENT FAILURES & MATERIAL FLOW PROPAGATION
        </div>
        <p style={{ margin: 0, fontSize: 12, lineHeight: 1.4, color: "var(--text-main)" }}>
          <strong>No Cascading Mechanical Breakdowns:</strong> Machines in Verdandi fail independently governed by individual Poisson MTTF wear. An upstream failure does <em>not</em> trigger secondary or related mechanical failures on downstream machines.
        </p>
        <p style={{ margin: 0, fontSize: 12, lineHeight: 1.4, color: "var(--text-main)" }}>
          <strong>Downstream Impact is Material Starvation (STARVED):</strong> When an upstream machine halts, downstream stations quickly exhaust their intermediate buffer cells and enter the <strong>STARVED</strong> state (blue). They remain mechanically healthy but idle awaiting material.
        </p>
        <p style={{ margin: 0, fontSize: 12, lineHeight: 1.4, color: "var(--text-main)" }}>
          <strong>Upstream Impact is Buffer Blocking (BLOCKED):</strong> When a downstream station halts, parts accumulate in intermediate buffers until capacity is reached, forcing upstream machines into the <strong>BLOCKED</strong> state (amber) to prevent buffer overflow.
        </p>
      </section>

      {/* Multi-Station State Heatmap */}
      <section
        className="sim-box"
        style={{
          background: "var(--paper-100)",
          border: "2px solid var(--ink-900)",
          padding: 14,
          boxShadow: "var(--shadow-card)",
        }}
      >
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            marginBottom: 8,
            flexWrap: "wrap",
            gap: 8,
          }}
        >
          <div>
            <h3 className="px-h3" style={{ margin: 0 }}>
              1. Multi-Station Operational State Heatmap (26 Machines × 300 Steps)
            </h3>
            <p style={{ fontSize: 12, color: "var(--text-muted)", margin: "2px 0 0 0" }}>
              Click anywhere on the timeline to scrub the simulation playhead to that step.
            </p>
          </div>

          {/* Color Legend */}
          <div style={{ display: "flex", gap: 12, alignItems: "center", fontSize: 11 }}>
            <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
              <span style={{ width: 10, height: 10, background: "#009e73", border: "1px solid #141b26" }} /> RUN
            </span>
            <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
              <span style={{ width: 10, height: 10, background: "#56b4e9", border: "1px solid #141b26" }} /> STARVED
            </span>
            <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
              <span style={{ width: 10, height: 10, background: "#e69f00", border: "1px solid #141b26" }} /> BLOCKED
            </span>
            <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
              <span style={{ width: 10, height: 10, background: "#d55e00", border: "1px solid #141b26" }} /> DOWN
            </span>
          </div>
        </div>

        <AnomalyHeatmap
          summary={summary}
          cursor={cursor}
          selectedId={selectedId}
          onSeek={source.stepTo}
          onSelectMachine={setSelectedId}
        />
      </section>

      {/* Incident Telemetry Ledger */}
      <section
        className="sim-box"
        style={{
          background: "var(--paper-100)",
          border: "2px solid var(--ink-900)",
          padding: 14,
          boxShadow: "var(--shadow-card)",
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 8, marginBottom: 10 }}>
          <div>
            <h3 className="px-h3" style={{ margin: 0 }}>
              2. Incident Telemetry Ledger ({filteredIncidents.length} Events Showing)
            </h3>
            <p style={{ margin: "2px 0 0 0", fontSize: 11, color: "var(--text-muted)" }}>
              Chronological ledger of mechanical wear, injected faults, logistics waits, quality verdicts, and sensor outliers.
            </p>
          </div>

          {/* Category Filter Tabs */}
          <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
            {[
              { id: "ALL", label: `ALL (${summary.incidents.length})` },
              { id: "MECHANICAL", label: `WEAR (${summary.mechanicalWearCount})` },
              { id: "INJECTED", label: `INJECTED (${summary.injectedFaultCount})` },
              { id: "LOGISTICS", label: `LOGISTICS (${summary.logisticsWaitCount})` },
              { id: "QUALITY", label: `QUALITY (${summary.qualityDefectCount})` },
              { id: "SENSOR", label: `SENSOR OUTLIERS (${summary.sensorDriftCount + summary.sensorBiasCount})` },
            ].map((cat) => (
              <button
                key={cat.id}
                type="button"
                className="px-btn"
                onClick={() => setSelectedCategory(cat.id)}
                style={{
                  fontSize: 10,
                  padding: "2px 6px",
                  background: selectedCategory === cat.id ? "var(--ink-900)" : "var(--paper-100)",
                  color: selectedCategory === cat.id ? "#fff" : "var(--ink-950)",
                  borderColor: "var(--ink-900)",
                }}
              >
                {cat.label}
              </button>
            ))}
          </div>
        </div>

        {filteredIncidents.length === 0 ? (
          <p style={{ fontSize: 13, color: "var(--text-muted)" }}>
            No events match the selected category filter for this episode.
          </p>
        ) : (
          <div
            style={{
              maxHeight: 250,
              overflowY: "auto",
              border: "1px solid var(--ink-900)",
              background: "var(--paper-50)",
            }}
          >
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
              <thead>
                <tr style={{ background: "var(--paper-300)", borderBottom: "1px solid var(--ink-900)", textAlign: "left" }}>
                  <th style={{ padding: "4px 8px" }}>STEP</th>
                  <th style={{ padding: "4px 8px" }}>STATION</th>
                  <th style={{ padding: "4px 8px" }}>CATEGORY</th>
                  <th style={{ padding: "4px 8px" }}>CLASSIFICATION & ROOT CAUSE</th>
                  <th style={{ padding: "4px 8px" }}>ACTION</th>
                </tr>
              </thead>
              <tbody>
                {filteredIncidents.map((inc) => (
                  <tr
                    key={inc.id}
                    style={{
                      borderBottom: "1px solid var(--paper-200)",
                      background: inc.machine === selectedId ? "var(--paper-200)" : "transparent",
                    }}
                  >
                    <td style={{ padding: "4px 8px", fontFamily: "var(--font-mono, monospace)" }}>
                      t={inc.step}
                    </td>
                    <td style={{ padding: "4px 8px", fontWeight: "bold" }}>
                      {inc.machine}
                    </td>
                    <td style={{ padding: "4px 8px" }}>
                      <span
                        className="px-badge"
                        style={{
                          background:
                            inc.type === "injected"
                              ? "var(--state-down)"
                              : inc.category === "mechanical"
                                ? "var(--series-sensor)"
                                : inc.category === "logistics_wait"
                                  ? "var(--state-starved)"
                                  : inc.category === "quality_defect"
                                    ? "var(--state-blocked)"
                                    : "var(--ink-700)",
                          color: "#fff",
                          padding: "1px 6px",
                          fontSize: 9,
                        }}
                      >
                        {inc.categoryLabel}
                      </span>
                    </td>
                    <td style={{ padding: "4px 8px" }}>{inc.detail}</td>
                    <td style={{ padding: "4px 8px" }}>
                      <button
                        type="button"
                        className="px-btn"
                        onClick={() => {
                          source.stepTo(inc.step);
                          setSelectedId(inc.machine);
                        }}
                        style={{ fontSize: 10, padding: "2px 6px" }}
                        title={`Jump simulation to step ${inc.step}`}
                      >
                        Jump to t={inc.step}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* Telemetry Stream Health & Continuous Statistical Detection */}
      <section
        className="sim-box"
        style={{
          background: "var(--paper-100)",
          border: "2px solid var(--ink-900)",
          padding: 14,
          boxShadow: "var(--shadow-card)",
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 8 }}>
          <h3 className="px-h3" style={{ margin: 0 }}>
            3. Continuous Sensor Telemetry Integrity (26 Station Channels)
          </h3>
          <span
            className="px-badge"
            style={{
              background: summary.sensorAnomalyCount === 0 ? "var(--state-run)" : "var(--state-blocked)",
              color: "#fff",
              border: "1px solid var(--ink-900)",
              fontSize: 10,
              padding: "2px 8px",
            }}
          >
            {summary.sensorAnomalyCount === 0
              ? "100% NOMINAL — 0 STATISTICAL OUTLIERS"
              : `${summary.sensorAnomalyCount} STATISTICAL OUTLIERS (>3σ)`}
          </span>
        </div>
        <p style={{ fontSize: 13, color: "var(--text-main)", marginTop: 8, lineHeight: 1.4 }}>
          Live process verification across all 26 machine vibration, thermal, and current telemetry streams. Nominal baseline physics maintains calibrated Gaussian variance around baseline. When sensor drift, bias, or cyber-physical anomalies are injected, the real-time detector flags observations deviating beyond the 3-sigma tolerance threshold.
        </p>
      </section>

      {/* Digital Twin Anomaly & Fault Mode Taxonomy Matrix */}
      <section
        className="sim-box"
        style={{
          background: "var(--paper-100)",
          border: "2px solid var(--ink-900)",
          padding: 14,
          boxShadow: "var(--shadow-card)",
        }}
      >
        <h3 className="px-h3" style={{ margin: "0 0 8px 0" }}>
          4. Digital Twin Anomaly &amp; Fault Mode Taxonomy
        </h3>
        <p style={{ fontSize: 12, color: "var(--text-muted)", margin: "0 0 10px 0" }}>
          Comprehensive reference of all 7 anomaly and disruption modes supported by the Verdandi digital twin architecture:
        </p>

        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 11, background: "var(--paper-50)", border: "1px solid var(--ink-900)" }}>
            <thead>
              <tr style={{ background: "var(--paper-300)", borderBottom: "1px solid var(--ink-900)", textAlign: "left" }}>
                <th style={{ padding: "6px 8px" }}>FAULT CLASS</th>
                <th style={{ padding: "6px 8px" }}>PHYSICAL PHENOMENON</th>
                <th style={{ padding: "6px 8px" }}>TELEMETRY SIGNATURE</th>
                <th style={{ padding: "6px 8px" }}>FACTORY LINE IMPACT</th>
              </tr>
            </thead>
            <tbody>
              <tr style={{ borderBottom: "1px solid var(--paper-200)" }}>
                <td style={{ padding: "6px 8px", fontWeight: "bold" }}>Mechanical Wear</td>
                <td style={{ padding: "6px 8px" }}>Component fatigue &amp; motor breakdown (Poisson MTTF)</td>
                <td style={{ padding: "6px 8px" }}>State transitions to DOWN; motor current drops to 0</td>
                <td style={{ padding: "6px 8px" }}>Station halts; downstream starved, upstream blocked</td>
              </tr>
              <tr style={{ borderBottom: "1px solid var(--paper-200)" }}>
                <td style={{ padding: "6px 8px", fontWeight: "bold" }}>Sensor Drift</td>
                <td style={{ padding: "6px 8px" }}>Gradual calibration decay / sensor degradation</td>
                <td style={{ padding: "6px 8px" }}>Linear slope drift away from baseline (&gt;3σ)</td>
                <td style={{ padding: "6px 8px" }}>Silent telemetry degradation without immediate line halt</td>
              </tr>
              <tr style={{ borderBottom: "1px solid var(--paper-200)" }}>
                <td style={{ padding: "6px 8px", fontWeight: "bold" }}>Sensor Bias / Spike</td>
                <td style={{ padding: "6px 8px" }}>Constant DC offset shift or transient electrical pulse</td>
                <td style={{ padding: "6px 8px" }}>Instantaneous step shift ±4..10σ in observation</td>
                <td style={{ padding: "6px 8px" }}>False-alarm trips in SCADA threshold monitoring</td>
              </tr>
              <tr style={{ borderBottom: "1px solid var(--paper-200)" }}>
                <td style={{ padding: "6px 8px", fontWeight: "bold" }}>Process Delay</td>
                <td style={{ padding: "6px 8px" }}>Thermal friction / mechanical slowdown extending cycle time</td>
                <td style={{ padding: "6px 8px" }}>Extended cycle time d (+3..6 steps per part)</td>
                <td style={{ padding: "6px 8px" }}>Throughput bottlenecks, upstream buffer congestion</td>
              </tr>
              <tr style={{ borderBottom: "1px solid var(--paper-200)" }}>
                <td style={{ padding: "6px 8px", fontWeight: "bold" }}>Material / Yield Loss</td>
                <td style={{ padding: "6px 8px" }}>In-process workpiece drop or ejection failure</td>
                <td style={{ padding: "6px 8px" }}>Drop rate 0.10..0.30; parts disappear mid-flow</td>
                <td style={{ padding: "6px 8px" }}>Downstream stations starved unexpectedly with no breakdown</td>
              </tr>
              <tr style={{ borderBottom: "1px solid var(--paper-200)" }}>
                <td style={{ padding: "6px 8px", fontWeight: "bold" }}>Quality Defect &amp; Rework</td>
                <td style={{ padding: "6px 8px" }}>Machining out-of-tolerance detected at INSP0 / ASM2</td>
                <td style={{ padding: "6px 8px" }}>Quality verdict REJECT/DEGRADE; routing to RWK0</td>
                <td style={{ padding: "6px 8px" }}>Defective assemblies routed to RWK0 Rework Bay loop</td>
              </tr>
              <tr>
                <td style={{ padding: "6px 8px", fontWeight: "bold" }}>Logistics AGV Wait</td>
                <td style={{ padding: "6px 8px" }}>Automated Guided Vehicle transport corridor contention</td>
                <td style={{ padding: "6px 8px" }}>AGV_WAIT events emitted with wait and hold timers</td>
                <td style={{ padding: "6px 8px" }}>Assembly ASM0 starved of kit kits; tail buffers hold parts</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
