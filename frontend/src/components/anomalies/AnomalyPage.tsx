import { useTwinStream } from "../../sim/TwinStreamProvider";

export function AnomalyPage(): React.JSX.Element {
  const { source, episodeId, selectedId, faults } = useTwinStream();

  return (
    <div
      className="anomaly-page-container"
      data-testid="anomaly-page"
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
            Plant Anomaly Detection & Diagnostic Horizon
          </h2>
          <p style={{ margin: "4px 0 0 0", color: "var(--text-muted)", fontSize: 13 }}>
            Continuous multi-station state heatmap, fault injection provenance, and synchronized telemetry bands.
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

      {/* Placeholder timeline to be replaced with full interactive Gantt in M5 */}
      <section
        className="sim-box"
        style={{
          background: "var(--paper-100)",
          border: "2px solid var(--ink-900)",
          padding: 16,
          boxShadow: "var(--shadow-card)",
        }}
      >
        <h3 className="px-h3" style={{ margin: "0 0 8px 0" }}>
          1. Multi-Station Operational State Timeline (0 .. 300 Steps)
        </h3>
        <p style={{ fontSize: 13, color: "var(--text-muted)" }}>
          Synchronized state tracking across all 26 manufacturing stations. Active station: <strong>{selectedId}</strong>
        </p>
        <div
          style={{
            height: 120,
            background: "var(--paper-300)",
            border: "2px solid var(--ink-900)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontFamily: "var(--font-mono)",
            fontSize: 16,
          }}
        >
          [State Timeline Heatmap Engine Loading...]
        </div>
      </section>

      {/* Fault & Incident Cards */}
      <section
        className="sim-box"
        style={{
          background: "var(--paper-100)",
          border: "2px solid var(--ink-900)",
          padding: 16,
          boxShadow: "var(--shadow-card)",
        }}
      >
        <h3 className="px-h3" style={{ margin: "0 0 8px 0" }}>
          2. Ground Truth & Anomaly Horizon
        </h3>
        {faults.length === 0 ? (
          <p style={{ fontSize: 13, color: "var(--text-muted)" }}>
            No active faults detected at current step ({source.cursor}). Nominal operation.
          </p>
        ) : (
          <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
            {faults.map((f) => (
              <div
                key={f.id}
                style={{
                  background: "var(--paper-50)",
                  border: "2px solid var(--state-down)",
                  padding: 8,
                  fontSize: 13,
                }}
              >
                <strong>{f.id}</strong>: {f.class} on {f.origin} (t0={f.t0}, dur={f.dur})
              </div>
            ))}
          </div>
        )}
      </section>

      {/* ML Detector Preview */}
      <section
        className="sim-box"
        style={{
          background: "var(--paper-100)",
          border: "2px dashed var(--ink-700)",
          padding: 16,
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h3 className="px-h3" style={{ margin: 0 }}>
            3. Automated Anomaly Detector
          </h3>
          <span
            style={{
              background: "var(--paper-300)",
              border: "1px solid var(--ink-900)",
              fontSize: 11,
              fontWeight: "bold",
              padding: "2px 6px",
            }}
          >
            LAYOUT PREVIEW — COMING SOON
          </span>
        </div>
        <p style={{ fontSize: 13, color: "var(--text-muted)", marginTop: 8 }}>
          Machine learning anomaly detection scores, precision/recall curves, and learned causal graph inference.
        </p>
      </section>
    </div>
  );
}
