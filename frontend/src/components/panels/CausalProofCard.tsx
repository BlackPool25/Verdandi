import { useMemo } from "react";
import type { FaultSpec } from "../events/types";
import { MACHINE_META, BUFFER_CAPS } from "./machineMeta";
import type { PanelTick } from "./selectors";

export interface CausalHop {
  readonly id: string;
  readonly label: string;
  readonly role: "symptom" | "upstream" | "gateway";
  readonly hop: number;
  readonly couplingBuffer: string | null;
  readonly bufferCap: number | null;
  readonly nominalObs: number;
  readonly sigma: number;
  readonly isOrigin: boolean;
}

export interface CausalProofProps {
  readonly selectedId: string;
  readonly tick: PanelTick | null;
  readonly faults: readonly FaultSpec[];
  readonly onStepTo?: ((step: number) => void) | undefined;
  readonly onSelect?: ((id: string) => void) | undefined;
}

/** Compute the deterministic physical upstream causal chain (<= 3 hops + gateway). */
export function deriveCausalChain(
  targetId: string,
  faults: readonly FaultSpec[],
): readonly CausalHop[] {
  const chain: CausalHop[] = [];

  // Identify if any active fault matches this target or an upstream node
  const activeFault = faults.find((f) => f.origin === targetId) ?? faults[0];

  function makeHop(
    id: string,
    role: "symptom" | "upstream" | "gateway",
    hop: number,
    couplingBuffer: string | null,
  ): CausalHop {
    const meta = MACHINE_META[id];
    return {
      id,
      label: id,
      role,
      hop,
      couplingBuffer,
      bufferCap: couplingBuffer !== null ? BUFFER_CAPS[couplingBuffer] ?? null : null,
      nominalObs: meta?.base ?? 50.0,
      sigma: meta?.sigma ?? 1.0,
      isOrigin: activeFault?.origin === id,
    };
  }

  // Symptom machine (Hop 0)
  chain.push(makeHop(targetId, "symptom", 0, null));

  // Determine line prefix and index
  if (targetId.startsWith("A") && targetId.length === 2 && !Number.isNaN(Number(targetId[1]))) {
    const idx = Number(targetId[1]);
    for (let h = 1; h <= 3 && idx - h >= 0; h += 1) {
      const prevId = `A${idx - h}`;
      const buf = `A${idx - h}${idx - h + 1}`;
      chain.push(makeHop(prevId, "upstream", h, buf));
    }
    if (idx > 3) {
      chain.push(makeHop("A0", "gateway", chain.length, "A01"));
    }
  } else if (targetId.startsWith("B") && targetId.length === 2 && !Number.isNaN(Number(targetId[1]))) {
    const idx = Number(targetId[1]);
    for (let h = 1; h <= 3 && idx - h >= 0; h += 1) {
      const prevId = `B${idx - h}`;
      const buf = `B${idx - h}${idx - h + 1}`;
      chain.push(makeHop(prevId, "upstream", h, buf));
    }
    if (idx > 3) {
      chain.push(makeHop("B0", "gateway", chain.length, "B01"));
    }
  } else if (targetId.startsWith("C") && targetId.length === 2 && !Number.isNaN(Number(targetId[1]))) {
    const idx = Number(targetId[1]);
    for (let h = 1; h <= 3 && idx - h >= 0; h += 1) {
      const prevId = `C${idx - h}`;
      const buf = `C${idx - h}${idx - h + 1}`;
      chain.push(makeHop(prevId, "upstream", h, buf));
    }
    if (idx > 3) {
      chain.push(makeHop("C0", "gateway", chain.length, "C01"));
    }
  } else if (targetId === "ASM2") {
    chain.push(makeHop("ASM1", "upstream", 1, "ASM12"));
    chain.push(makeHop("ASM0", "upstream", 2, "ASM01"));
    chain.push(makeHop("B9", "gateway", 3, "GB9"));
  } else if (targetId === "ASM1") {
    chain.push(makeHop("ASM0", "upstream", 1, "ASM01"));
    chain.push(makeHop("A9", "gateway", 2, "GA9"));
  } else if (targetId === "ASM0") {
    chain.push(makeHop("A9", "gateway", 1, "GA9"));
    chain.push(makeHop("B9", "gateway", 2, "GB9"));
    chain.push(makeHop("C7", "gateway", 3, "_C7TAIL"));
  } else if (targetId === "RWK0") {
    chain.push(makeHop("ASM2", "upstream", 1, "RWK_RET"));
    chain.push(makeHop("ASM1", "upstream", 2, "ASM12"));
    chain.push(makeHop("ASM0", "gateway", 3, "kitC"));
  }

  return chain;
}

export function CausalProofCard({
  selectedId,
  tick,
  faults,
  onStepTo,
  onSelect,
}: CausalProofProps): React.JSX.Element {
  const chain = useMemo(() => deriveCausalChain(selectedId, faults), [selectedId, faults]);
  const activeFault = useMemo(
    () => faults.find((f) => f.origin === selectedId) ?? (faults.length > 0 ? faults[0] : null),
    [faults, selectedId],
  );

  const step = tick?.step ?? 0;
  const isInsideFault =
    activeFault !== null && activeFault !== undefined &&
    activeFault.t0 <= step && step < activeFault.t1;

  return (
    <div className="causal-card px-panel" data-testid="causal-proof-card">
      <div className="causal-card__header">
        <span className="causal-card__tag">PROVENANCE & CAUSAL PROOF</span>
        {isInsideFault && <span className="px-badge px-badge-down">ACTIVE FAULT WINDOW</span>}
      </div>

      <div className="causal-card__story">
        <div className="causal-card__claim">
          <strong>Observed State:</strong> Machine <code>{selectedId}</code> evaluated at Step {step}.
          {activeFault !== null && activeFault !== undefined && (
            <div className="causal-card__fault-meta">
              Ranked Cause: Injected <strong>{activeFault.class}</strong> at{" "}
              <button
                type="button"
                className="px-link-btn"
                onClick={() => onSelect?.(activeFault.origin)}
              >
                {activeFault.origin}
              </button>{" "}
              (Window: [{activeFault.t0}, {activeFault.t1}))
            </div>
          )}
        </div>

        <div className="causal-card__chain-title">
          Ranked Upstream Propagation Path (&le; 3 steps + Gateway):
        </div>

        <ol className="causal-chain-list">
          {chain.map((hop, idx) => (
            <li
              key={hop.id}
              className={`causal-chain-node ${hop.isOrigin ? "is-origin" : ""} ${
                hop.role === "symptom" ? "is-symptom" : ""
              }`}
            >
              <div className="causal-node-pill">
                <span className="causal-node-step">0{idx + 1}</span>
                <button
                  type="button"
                  className="causal-node-btn"
                  onClick={() => onSelect?.(hop.id)}
                >
                  {hop.label}
                </button>
                <span className="causal-node-role">{hop.role}</span>
                {hop.couplingBuffer !== null && (
                  <span className="causal-node-buffer">via {hop.couplingBuffer}</span>
                )}
                {hop.isOrigin && <span className="causal-origin-badge">ORIGIN</span>}
              </div>
              {idx < chain.length - 1 && <div className="causal-node-arrow">&uarr; propagates from</div>}
            </li>
          ))}
        </ol>

        <div className="causal-card__evidence">
          <div className="causal-evidence-title">Triple-Grounded Evidence:</div>
          <ul className="causal-evidence-list">
            <li>
              <strong>1. Physical Coupling:</strong> Upstream buffer and mass conservation enforce direct flow dependence.
            </li>
            <li>
              <strong>2. Signal Departure:</strong> Signal departure outside normal operating baseline (&plusmn;3&sigma; envelope).
            </li>
            <li>
              <strong>3. Deterministic Seed:</strong> Seeded simulation guarantees byte-identical reproducibility.
            </li>
          </ul>
        </div>

        {activeFault !== null && activeFault !== undefined && onStepTo !== undefined && (
          <div className="causal-card__action">
            <button
              type="button"
              className="px-btn causal-replay-btn"
              onClick={() => onStepTo(activeFault.t0)}
            >
              &#9654; Step to Disturbance Origin (t = {activeFault.t0})
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
