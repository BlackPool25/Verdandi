// T8 selected-machine faceplate rail (360px): probe selector + live values
// from the tick payload row via machinePanelFor — never invented. Sections
// render verbatim from machinePanelFor (class/signal/timing/reliability/
// buffer & routing); the sparkline is the shared StripChart for the selected
// machine (B7P fallback for stores/empty — the rail always mounts one chart).
import { machinePanelFor, sbufPanelFor, tailPathFor, type PanelTick } from "./selectors";
import { MACHINE_META } from "./machineMeta";
import { StripChart } from "../charts/StripChart";
import type { TwinStore } from "../../store/twinStore";
import type { FaultSpec } from "../events/types";
import { CausalProofCard } from "./CausalProofCard";

// L4 faceplate probes: one id per machine class (9 classes).
export const FACEPLATE_IDS: readonly string[] = [
  "A0",
  "A2",
  "A8",
  "A9",
  "B2",
  "C7",
  "ASM1",
  "ASM2",
  "RWK0",
];

const OTHER_IDS: readonly string[] = Object.keys(MACHINE_META).filter(
  (id) => !FACEPLATE_IDS.includes(id),
);

// Stores ride the faceplate too (no per-step series, never in machinePanelFor).
const SPECIAL_IDS: readonly string[] = ["_C7TAIL", "SBUF"];

export interface MachinePanelProps {
  readonly tick: PanelTick | null;
  readonly selectedId: string | null;
  readonly onSelect?: (id: string) => void;
  readonly store?: TwinStore | null;
  readonly faults?: readonly FaultSpec[];
  readonly onStepTo?: (step: number) => void;
}

const WRAP: React.CSSProperties = { overflowWrap: "anywhere" };

const ROW: React.CSSProperties = {
  listStyle: "none",
  margin: 0,
  padding: 0,
  display: "flex",
  flexWrap: "wrap",
  gap: 4,
};

function FaceplateNav(props: {
  readonly selectedId: string | null;
  readonly onSelect: (id: string) => void;
}): React.JSX.Element {
  return (
    <nav aria-label="machine faceplate" data-testid="machine-faceplate" className="faceplate-nav">
      <div className="faceplate-nav__group-label">PRIMARY PROBES:</div>
      <ul style={ROW} className="faceplate-btn-list">
        {FACEPLATE_IDS.map((id) => (
          <li key={id}>
            <button
              type="button"
              className={`px-btn faceplate-btn ${props.selectedId === id ? "active" : ""}`}
              data-testid={`select-${id}`}
              aria-pressed={props.selectedId === id}
              onClick={() => props.onSelect(id)}
            >
              {id}
            </button>
          </li>
        ))}
      </ul>
      <div className="faceplate-nav__group-label">ALL STATIONS & STORES:</div>
      <ul style={ROW} className="faceplate-btn-list">
        {OTHER_IDS.map((id) => (
          <li key={id}>
            <button
              type="button"
              className={`px-btn faceplate-btn ${props.selectedId === id ? "active" : ""}`}
              data-testid={`select-${id}`}
              aria-pressed={props.selectedId === id}
              onClick={() => props.onSelect(id)}
            >
              {id}
            </button>
          </li>
        ))}
        {SPECIAL_IDS.map((id) => (
          <li key={id}>
            <button
              type="button"
              className={`px-btn faceplate-btn ${props.selectedId === id ? "active" : ""}`}
              data-testid={`select-${id}`}
              aria-pressed={props.selectedId === id}
              onClick={() => props.onSelect(id)}
            >
              {id}
            </button>
          </li>
        ))}
      </ul>
    </nav>
  );
}

export function MachinePanel(props: MachinePanelProps): React.JSX.Element {
  const { tick, selectedId, onSelect, store, faults = [], onStepTo } = props;
  const nav =
    onSelect === undefined ? null : <FaceplateNav selectedId={selectedId} onSelect={onSelect} />;
  // Rail invariant: exactly one sparkline mounted whenever the store is
  // wired (storms e2e asserts strip-B2 visible with nothing selected), plus
  // the CH8 motor-current strip for the same machine.
  const faceId =
    selectedId !== null && MACHINE_META[selectedId] !== undefined ? selectedId : "B2";

  const meta = selectedId !== null ? MACHINE_META[selectedId] : undefined;
  const obsMin = meta !== undefined ? Math.max(0, Math.floor(meta.base - 4 * meta.sigma)) : 0;
  const obsMax = meta !== undefined ? Math.ceil(meta.base + 4 * meta.sigma) : 100;

  const sparkline =
    store === undefined || store === null ? null : (
      <div className="machine-panel__sparklines">
        <StripChart
          store={store}
          machineId={faceId}
          title="OBSERVATION TELEMETRY (RING BUFFER)"
          width={280}
          height={68}
          min={obsMin}
          max={obsMax}
          unit="units"
        />
        <StripChart
          store={store}
          machineId={faceId}
          title="MOTOR CURRENT, A (CH8)"
          width={280}
          height={68}
          min={0}
          max={20}
          source="current"
          testidSuffix="-current"
          unit="Amps (A)"
        />
      </div>
    );

  if (tick === null || selectedId === null) {
    return (
      <section aria-label="machine panel" data-testid="machine-panel" className="sim-box px-panel machine-detail-panel">
        <div className="faceplate-header-sticky">
          <h2 className="px-h2 panel-title">Machine Inspector</h2>
          {nav}
        </div>
        <p data-testid="machine-panel-empty" className="empty-selection-note">No machine selected.</p>
        {sparkline}
      </section>
    );
  }

  if (selectedId === "SBUF") {
    const sbuf = sbufPanelFor(tick);
    const sbufSparkline =
      store === undefined || store === null ? null : (
        <div className="machine-panel__sparklines">
          <StripChart
            store={store}
            machineId="SBUF"
            title="SBUF OCCUPANCY (BUFFER STORE)"
            width={280}
            height={68}
            min={0}
            max={30}
            source="buffer"
            unit="parts"
          />
        </div>
      );

    return (
      <section aria-label="machine panel" data-testid="machine-panel" className="sim-box px-panel machine-detail-panel">
        <div className="faceplate-header-sticky">
          <div className="machine-panel-header">
            <h2 className="px-h2 panel-title">Machine SBUF</h2>
            <span className={`px-badge ${sbuf.high ? "px-badge-down" : "px-badge-run"}`}>
              {sbuf.high ? "HIGH UTIL" : "NORMAL"}
            </span>
          </div>
          {nav}
        </div>
        <dl className="machine-specs-grid">
          <div><dt>level</dt><dd data-testid="machine-panel-sbuf-level" style={WRAP}>{sbuf.level}</dd></div>
          <div><dt>cap</dt><dd data-testid="machine-panel-sbuf-cap" style={WRAP}>{sbuf.cap}</dd></div>
          <div><dt>high-util</dt><dd data-testid="machine-panel-sbuf-high" style={WRAP}>{sbuf.high ? "high" : "ok"}</dd></div>
          <div><dt>occupancy</dt><dd style={WRAP}>{Math.round((sbuf.level / sbuf.cap) * 100)}%</dd></div>
        </dl>
        <p data-testid="machine-panel-sbuf-label" className="path-note">{sbuf.noSeriesLabel}</p>
        <p className="path-note">Path: SBUF-divert store (process/finish/inspect-tail only).</p>
        {sbufSparkline ?? sparkline}
      </section>
    );
  }

  const panel = machinePanelFor(tick, selectedId);
  if (!panel.found) {
    return (
      <section aria-label="machine panel" data-testid="machine-panel" className="sim-box px-panel machine-detail-panel">
        <div className="faceplate-header-sticky">
          <h2 className="px-h2 panel-title">Machine {selectedId}</h2>
          {nav}
        </div>
        <p data-testid="machine-panel-empty" className="empty-selection-note">Unknown machine id — no data.</p>
        {sparkline}
      </section>
    );
  }

  if (panel.kind === "c7tail") {
    return (
      <section aria-label="machine panel" data-testid="machine-panel" className="sim-box px-panel machine-detail-panel">
        <div className="faceplate-header-sticky">
          <div className="machine-panel-header">
            <h2 className="px-h2 panel-title">Machine _C7TAIL</h2>
            <span className="px-badge px-badge-run">STORE TAIL</span>
          </div>
          {nav}
        </div>
        <dl className="machine-specs-grid">
          <div>
            <dt>final output</dt>
            <dd data-testid="machine-panel-c7tail-final" style={WRAP}>
              {panel.c7tailFinal === null ? "no episode yet" : panel.c7tailFinal}
            </dd>
          </div>
          <div><dt>drain method</dt><dd style={WRAP}>AGV transport</dd></div>
          <div><dt>source</dt><dd style={WRAP}>Station C7</dd></div>
          <div><dt>status</dt><dd style={WRAP}>ACCUMULATING</dd></div>
        </dl>
        <p data-testid="machine-panel-c7tail-label" className="path-note">{panel.noSeriesLabel}</p>
        <p className="path-note">Path: AGV-drained store (C7 tail).</p>
        {sparkline}
      </section>
    );
  }

  const machineIdx = tick.machineOrder.indexOf(panel.id);
  const currentVal = machineIdx >= 0 && tick.currents ? tick.currents[machineIdx] : null;

  return (
    <section aria-label="machine panel" data-testid="machine-panel" className="sim-box px-panel machine-detail-panel">
      <div className="faceplate-header-sticky">
        <div className="machine-panel-header">
          <h2 className="px-h2 panel-title">Machine {panel.id}</h2>
          <span className={`px-badge px-badge-${panel.state.toLowerCase()}`}>{panel.state}</span>
        </div>
        {nav}
      </div>
      <dl className="machine-specs-grid">
        <div><dt>state</dt><dd data-testid="machine-panel-state" style={WRAP}>{panel.state}</dd></div>
        <div><dt>obs</dt><dd data-testid="machine-panel-obs" style={WRAP}>{typeof panel.obs === "number" ? panel.obs.toFixed(2) : panel.obs}</dd></div>
        <div><dt>current</dt><dd data-testid="machine-panel-current" style={WRAP}>{typeof currentVal === "number" ? `${currentVal.toFixed(2)} A` : "—"}</dd></div>
        <div><dt>envelope</dt><dd data-testid="machine-panel-envelope" style={WRAP}>{panel.envelopeNote}</dd></div>
        <div><dt>tput</dt><dd data-testid="machine-panel-tput" style={WRAP}>{panel.tput}</dd></div>
        <div>
          <dt>last flag</dt>
          <dd data-testid="machine-panel-flag" style={WRAP}>{typeof panel.flag === "string" ? panel.flag : JSON.stringify(panel.flag)}</dd>
        </div>
        <div><dt>cycle</dt><dd data-testid="machine-panel-cycle" style={WRAP}>{panel.meta.cycle}</dd></div>
        <div><dt>mttf</dt><dd data-testid="machine-panel-mttf" style={WRAP}>{panel.meta.mttf}</dd></div>
        <div><dt>mttr</dt><dd data-testid="machine-panel-mttr" style={WRAP}>{panel.meta.mttr}</dd></div>
        <div><dt>path</dt><dd data-testid="machine-panel-path" style={WRAP}>{tailPathFor(panel.id)}</dd></div>
      </dl>
      {panel.sections.map((section) => (
        <section key={section.heading} aria-label={`config ${section.heading}`} className="config-section">
          <h3 className="px-h3 section-title">{section.heading}</h3>
          <dl className="config-specs-grid">
            {section.rows.map((row) => (
              <div key={row.testId}><dt>{row.label}</dt><dd data-testid={row.testId} style={WRAP}>{row.value}</dd></div>
            ))}
          </dl>
        </section>
      ))}
      {sparkline}
      <CausalProofCard
        selectedId={panel.id}
        tick={tick}
        faults={faults}
        onStepTo={onStepTo}
        onSelect={onSelect}
      />
      <details className="raw-json-details">
        <summary>raw JSON</summary>
        <pre data-testid="machine-panel-raw" style={{ ...WRAP, whiteSpace: "pre-wrap" }}>{panel.rawJson}</pre>
      </details>
    </section>
  );
}
