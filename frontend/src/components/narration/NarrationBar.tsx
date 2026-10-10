import { useEffect, useRef, useState } from "react";
import type { PanelTick } from "../panels/selectors";
import type { FaultSpec, TwinEvent } from "../events/types";
import { BUFFER_CAPS } from "../panels/machineMeta";
import "./narration.css";

export interface NarrationBarProps {
  readonly tick: PanelTick | null;
  readonly events?: readonly TwinEvent[];
  readonly faults: readonly FaultSpec[];
  readonly onSelectMachine?: (machineId: string) => void;
}

interface NarrationState {
  readonly text: string;
  readonly priority: number; // 5: FAULT, 4: DOWN, 3: BUFFER_FULL, 2: STARVED, 1: NORMAL
  readonly targetMachine?: string | undefined;
  readonly timestamp: number;
}

export function NarrationBar({
  tick,
  faults,
  onSelectMachine,
}: NarrationBarProps): React.JSX.Element {
  const [current, setCurrent] = useState<NarrationState>({
    text: "Factory initializing. Waiting for simulation stream…",
    priority: 1,
    timestamp: Date.now(),
  });

  const currentRef = useRef<NarrationState>(current);
  currentRef.current = current;

  useEffect(() => {
    if (!tick) return;
    const now = Date.now();
    const step = tick.step;

    let candidateText = `Step ${step}: Production running normally.`;
    let candidatePriority = 1;
    let candidateMachine: string | undefined = undefined;

    // 1. Check for Active Faults (Priority 5)
    if (faults.length > 0) {
      const f = faults[0];
      if (f) {
        candidateText = `Step ${step}: Injected fault active on Machine ${f.origin} (${f.class}).`;
        candidatePriority = 5;
        candidateMachine = f.origin;
      }
    }

    // 2. Check for DOWN machines (Priority 4)
    if (candidatePriority < 5) {
      const downIndices: number[] = [];
      tick.states.forEach((st, idx) => {
        if (st === "DOWN") downIndices.push(idx);
      });
      if (downIndices.length > 0) {
        const mId = tick.machineOrder[downIndices[0]!] ?? "Unknown";
        candidateText = `Step ${step}: Machine ${mId} broke down. WIP buffer accumulating.`;
        candidatePriority = 4;
        candidateMachine = mId;
      }
    }

    // 3. Check for Buffer Full (Priority 3)
    if (candidatePriority < 4) {
      let fullBufId: string | null = null;
      let fullCap = 0;
      tick.buffers.forEach((level, idx) => {
        const bId = Object.keys(BUFFER_CAPS)[idx];
        if (bId) {
          const cap = BUFFER_CAPS[bId] ?? 20;
          if (level >= cap) {
            fullBufId = bId;
            fullCap = cap;
          }
        }
      });
      if (fullBufId) {
        candidateText = `Step ${step}: Buffer ${fullBufId} is FULL (${fullCap}/${fullCap}). Upstream flow congested.`;
        candidatePriority = 3;
      }
    }

    // 4. Check for Starved / Congestion (Priority 2)
    if (candidatePriority < 3) {
      const starvedCount = tick.states.filter((st) => st === "STARVED").length;
      if (starvedCount > 8) {
        candidateText = `Step ${step}: ${starvedCount} machines waiting for parts from upstream lines.`;
        candidatePriority = 2;
      }
    }

    // 5. Normal Running (Priority 1)
    if (candidatePriority === 1) {
      const runningCount = tick.states.filter((st) => st === "RUN").length;
      candidateText = `Step ${step}: Normal flow. ${runningCount} of 26 machines operating.`;
    }

    // Dwell time evaluation: hold each message for at least 1500ms
    // unless candidate has higher priority.
    const dwellMs = 1500;
    const timeSinceLast = now - currentRef.current.timestamp;
    const isHigherPriority = candidatePriority > currentRef.current.priority;
    const hasDweltLongEnough = timeSinceLast >= dwellMs;

    if (isHigherPriority || (hasDweltLongEnough && candidateText !== currentRef.current.text)) {
      setCurrent({
        text: candidateText,
        priority: candidatePriority,
        targetMachine: candidateMachine,
        timestamp: now,
      });
    }
  }, [tick, faults]);

  const handleClick = () => {
    if (current.targetMachine && onSelectMachine) {
      onSelectMachine(current.targetMachine);
    }
  };

  return (
    <div
      className={`vd-narration-bar priority-${current.priority} ${current.targetMachine ? "is-clickable" : ""}`}
      role="status"
      aria-live="polite"
      aria-atomic="true"
      onClick={handleClick}
      title={current.targetMachine ? `Click to inspect machine ${current.targetMachine}` : undefined}
      data-testid="narration-bar"
    >
      <div className="vd-narration-icon" aria-hidden="true">
        {current.priority === 5 && "⚡"}
        {current.priority === 4 && "⚠"}
        {current.priority === 3 && "⏹"}
        {current.priority === 2 && "⏳"}
        {current.priority === 1 && "▶"}
      </div>
      <div className="vd-narration-text font-pixel">{current.text}</div>
      {current.targetMachine && (
        <span className="vd-narration-jump font-pixel">Inspect {current.targetMachine} ↗</span>
      )}
    </div>
  );
}
