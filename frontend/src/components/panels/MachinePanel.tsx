// T8 selected-machine panel. Pixel look matches MachineNode (dark #111,
// 1px border, VT323 body, Press Start 2P heading). Values come only from
// the tick payload row via machinePanelFor — never invented.
import { machinePanelFor, tailPathFor, type PanelTick } from "./selectors";

const BOX: React.CSSProperties = {
  border: "1px solid #888",
  background: "#111",
  color: "#eee",
  padding: 8,
  fontSize: 16,
};

export function MachinePanel(props: {
  readonly tick: PanelTick | null;
  readonly selectedId: string | null;
}): React.JSX.Element {
  const { tick, selectedId } = props;
  if (tick === null || selectedId === null) {
    return (
      <section aria-label="machine panel" data-testid="machine-panel" style={BOX}>
        <h2 className="px-h2">Machine</h2>
        <p data-testid="machine-panel-empty">No machine selected.</p>
      </section>
    );
  }
  const panel = machinePanelFor(tick, selectedId);
  if (!panel.found) {
    return (
      <section aria-label="machine panel" data-testid="machine-panel" style={BOX}>
        <h2 className="px-h2">Machine {selectedId}</h2>
        <p data-testid="machine-panel-empty">Unknown machine id — no data.</p>
      </section>
    );
  }
  if (panel.kind === "c7tail") {
    return (
      <section aria-label="machine panel" data-testid="machine-panel" style={BOX}>
        <h2 className="px-h2">Machine _C7TAIL</h2>
        <p data-testid="machine-panel-c7tail-final">
          final: {panel.c7tailFinal === null ? "no episode yet" : panel.c7tailFinal}
        </p>
        <p data-testid="machine-panel-c7tail-label">{panel.noSeriesLabel}</p>
        <p>Path: AGV-drained store (C7 tail).</p>
      </section>
    );
  }
  return (
    <section aria-label="machine panel" data-testid="machine-panel" style={BOX}>
      <h2 className="px-h2">Machine {panel.id}</h2>
      <dl>
        <div><dt>state</dt><dd data-testid="machine-panel-state">{panel.state}</dd></div>
        <div><dt>obs</dt><dd data-testid="machine-panel-obs">{panel.obs}</dd></div>
        <div><dt>envelope</dt><dd data-testid="machine-panel-envelope">{panel.envelopeNote}</dd></div>
        <div><dt>tput</dt><dd data-testid="machine-panel-tput">{panel.tput}</dd></div>
        <div>
          <dt>last flag</dt>
          <dd data-testid="machine-panel-flag">{JSON.stringify(panel.flag)}</dd>
        </div>
        <div><dt>cycle</dt><dd data-testid="machine-panel-cycle">{panel.meta.cycle}</dd></div>
        <div><dt>mttf</dt><dd data-testid="machine-panel-mttf">{panel.meta.mttf}</dd></div>
        <div><dt>mttr</dt><dd data-testid="machine-panel-mttr">{panel.meta.mttr}</dd></div>
        <div><dt>path</dt><dd data-testid="machine-panel-path">{tailPathFor(panel.id)}</dd></div>
      </dl>
    </section>
  );
}
