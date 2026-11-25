// Task 9 operator card: 3 cited claim rows, root/onset actions.
// Mirrors CausalProofCard onSelect/onStepTo signatures. Every claim chip
// carries its packet evidence id; clicks resolve to machine/step targets.
import type {
  DiagnosisCardData,
  DiagnosisClaim,
  DiagnosisPacket,
} from "./types";

export interface DiagnosisCardProps {
  readonly card: DiagnosisCardData;
  readonly packet: DiagnosisPacket;
  readonly onSelect?: ((id: string) => void) | undefined;
  readonly onStepTo?: ((step: number) => void) | undefined;
  readonly selectedId?: string | undefined;
}

function traceMachineFor(packet: DiagnosisPacket, evidenceId: string): string | null {
  const row = packet.trace.find((t) => t.id === evidenceId);
  return row?.machine ?? null;
}

function pathFirstNodeFor(packet: DiagnosisPacket, evidenceId: string): string | null {
  const row = packet.paths.find((p) => p.id === evidenceId);
  const first = row?.nodes[0];
  return first ?? null;
}

function claimTargetMachine(packet: DiagnosisPacket, claim: DiagnosisClaim): string | null {
  return (
    traceMachineFor(packet, claim.evidence_id) ?? pathFirstNodeFor(packet, claim.evidence_id)
  );
}

function formatValue(value: unknown): string {
  if (typeof value === "string") return value;
  if (typeof value === "number") return String(value);
  if (Array.isArray(value)) return value.map((v) => String(v)).join(" → ");
  if (value === null || value === undefined) return "—";
  return JSON.stringify(value) ?? "—";
}

export function DiagnosisCard({
  card,
  packet,
  onSelect,
  onStepTo,
  selectedId,
}: DiagnosisCardProps): React.JSX.Element | null {
  const handleChip = (claim: DiagnosisClaim): void => {
    const machine = claimTargetMachine(packet, claim);
    if (machine !== null) onSelect?.(machine);
  };
  return (
    <div className="causal-card px-panel" data-testid="diagnosis-card">
      <div className="causal-card__header">
        <span className="causal-card__tag">DIAGNOSIS — OPERATOR CARD</span>
        <span className="px-badge px-badge-run">{card.verdict}</span>
      </div>
      <div className="causal-card__story">
        <div className="causal-card__claim">
          <strong>Root:</strong> {card.root ?? "—"}{" "}
          {card.root !== null && (
            <button
              type="button"
              className="px-link-btn"
              data-testid={`diagnosis-root-${card.root}`}
              onClick={() => onSelect?.(card.root as string)}
            >
              inspect {card.root}
            </button>
          )}
        </div>
        <div className="causal-card__claim">
          <strong>Onset:</strong> {packet.onset ?? "—"}{" "}
          {packet.onset !== null && (
            <button
              type="button"
              className="px-btn"
              data-testid={`diagnosis-onset-${packet.onset}`}
              onClick={() => onStepTo?.(packet.onset as number)}
            >
              step to onset
            </button>
          )}
        </div>
        <div className="causal-card__chain-title">Cited claims (each carries packet evidence):</div>
        <ol className="causal-chain-list">
          {card.claims.map((claim) => {
            const target = claimTargetMachine(packet, claim);
            return (
              <li key={claim.evidence_id} className="causal-chain-node">
                <div className="causal-node-pill">
                  <span className="causal-node-role">{claim.text}</span>
                  <span>{formatValue(claim.value)}</span>
                  <button
                    type="button"
                    className="causal-node-btn"
                    data-testid={`diagnosis-chip-${claim.evidence_id}`}
                    aria-pressed={target !== null && target === selectedId}
                    onClick={() => handleChip(claim)}
                  >
                    {claim.evidence_id}
                  </button>
                </div>
              </li>
            );
          })}
        </ol>
        <div className="causal-card__evidence">
          <div className="causal-evidence-title">Action:</div>
          <ul className="causal-evidence-list">
            <li>{card.action}</li>
          </ul>
        </div>
      </div>
    </div>
  );
}
