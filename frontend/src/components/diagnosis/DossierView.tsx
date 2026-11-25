// Task 9 engineer dossier: full trace + paths, native <details> only.
// Closed by default; no fetch, no state beyond the element itself.
import type { DiagnosisDossier, DiagnosisPacket } from "./types";

export interface DossierViewProps {
  readonly dossier: DiagnosisDossier;
  readonly packet: DiagnosisPacket;
  readonly onSelect?: ((id: string) => void) | undefined;
  readonly onStepTo?: ((step: number) => void) | undefined;
}

export function DossierView({
  dossier,
  packet,
  onSelect,
  onStepTo,
}: DossierViewProps): React.JSX.Element | null {
  return (
    <details data-testid="diagnosis-dossier">
      <summary>dossier {dossier.packet_id ?? "unknown packet"}</summary>
      <p className="path-note">
        trigger {packet.trigger} · sensor {packet.sensor_verdict} · verdict{" "}
        {dossier.verdict ?? "—"}
      </p>
      <div className="causal-card__chain-title">Trace nodes:</div>
      <ol className="causal-chain-list">
        {dossier.nodes.map((node) => (
          <li key={node.evidence_id} className="causal-chain-node">
            <div
              className="causal-node-pill"
              data-testid={`diagnosis-node-${node.evidence_id}`}
            >
              <button
                type="button"
                className="causal-node-btn"
                onClick={() => onSelect?.(node.machine)}
              >
                {node.machine}
              </button>
              <span className="causal-node-role">onset {node.onset}</span>
              {node.onset_kind ? (
                <span className="causal-node-buffer">{node.onset_kind}</span>
              ) : null}
              {onStepTo !== undefined ? (
                <button type="button" className="px-link-btn" onClick={() => onStepTo(node.onset)}>
                  step to {node.onset}
                </button>
              ) : null}
            </div>
          </li>
        ))}
      </ol>
      <div className="causal-card__chain-title">Ranked paths:</div>
      <ol className="causal-chain-list">
        {dossier.paths.map((path) => (
          <li key={path.id} className="causal-chain-node">
            <div className="causal-node-pill" data-testid={`diagnosis-path-${path.id}`}>
              <button
                type="button"
                className="causal-node-btn"
                onClick={() => {
                  const first = path.nodes[0];
                  if (first !== undefined) onSelect?.(first);
                }}
              >
                {path.id}
              </button>
              <span className="causal-node-role">{path.nodes.join(" → ")}</span>
              <span className="causal-node-buffer">prob {path.prob}</span>
            </div>
          </li>
        ))}
      </ol>
    </details>
  );
}
