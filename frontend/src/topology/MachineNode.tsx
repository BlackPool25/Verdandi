import { memo } from "react";
import type { Node, NodeProps } from "@xyflow/react";
import { Handle, Position } from "@xyflow/react";
import "../components/events/events.css";
import spriteUrl from "../sprites/sprites.svg";
import { spriteFor, type MachineNodeDatum } from "./types";

export type MachineNodeType = Node<MachineNodeDatum, "machine">;

// Memo custom node: re-renders only when its own datum changes (per-tick
// updates flow through updateNodeData, never through layout or parents).
export const MachineNode = memo(function MachineNode({
  data,
}: NodeProps<MachineNodeType>): React.JSX.Element {
  // T9-owned anomaly region: overlay classes + ! glyph only. Topology
  // structure (handles, sizing, state testids) below stays T4-owned.
  const anomaly = data.anomaly;
  const overlayClass =
    anomaly?.gt === true
      ? "gt-outline"
      : anomaly?.down === "injected"
        ? "down-injected"
        : anomaly?.down === "natural"
          ? "down-natural"
          : anomaly?.neighbor === true
            ? "neighbor-highlight"
            : "";
  const glyph =
    anomaly?.gt === true || anomaly?.down === "injected" ? (
      <span
        data-testid={`node-glyph-${data.label}`}
        aria-label="fault"
        className="anomaly-glyph glyph-down-injected"
      >
        !
      </span>
    ) : anomaly?.down === "natural" ? (
      <span data-testid={`node-glyph-${data.label}`} aria-label="natural down" className="anomaly-glyph glyph-down-natural">
        !
      </span>
    ) : anomaly?.neighbor === true ? (
      <span data-testid={`node-glyph-${data.label}`} aria-label="congested neighbor" className="anomaly-glyph">
        !
      </span>
    ) : null;
  // T2 sprite: resolved from datum (cls/spriteId wired once in nodes.ts
  // via T1 spriteFor); absent = unresolved, falls back per-tick-safe.
  // Explicit 32x32 (2x of the 16x16 symbol grid) keeps dagre/fitView math
  // on the 120x60 card exact. Host svg stays visible (never display:none).
  const spriteId = data.spriteId ?? spriteFor(data.cls ?? "");
  // T3 status ring: gray base, green RUN, yellow STARVED/BLOCKED, red DOWN.
  // Flat string derived from datum only (memo-safe); rendered via
  // box-shadow classes in events.css so 120x60 dagre math never shifts.
  const ringClass =
    data.state === "RUN"
      ? "machine-ring-run"
      : data.state === "STARVED" || data.state === "BLOCKED"
        ? "machine-ring-warn"
        : data.state === "DOWN"
          ? "machine-ring-down"
          : "machine-ring-idle";
  const tput = data.tput ?? 0;
  return (
    <div
      data-testid={`node-${data.label}`}
      data-state={data.state ?? "unknown"}
      data-gt={anomaly?.gt === true ? "true" : "false"}
      data-down={anomaly?.down ?? ""}
      data-neighbor={anomaly?.neighbor === true ? "true" : "false"}
      className={["px-machine-node", ringClass, overlayClass].filter((c) => c !== "").join(" ")}
      style={{
        width: 120,
        height: 60,
      }}
    >
      <Handle type="target" position={Position.Left} />
      <div className="px-machine-header">
        <div className="px-machine-label">
          {data.label}
          {glyph}
        </div>
        <span className="px-machine-cls">{data.cls ?? data.kind ?? "mach"}</span>
      </div>
      <div className="px-machine-body">
        <svg
          width={32}
          height={32}
          aria-hidden="true"
          className="px-machine-sprite"
        >
          <use href={`${spriteUrl}#${spriteId}`} />
        </svg>
        <div className="px-machine-metrics">
          <div data-testid={`node-state-${data.label}`} className="px-machine-state">
            {data.state ?? "—"}
          </div>
          <div className="px-machine-tput-row">
            <span>OUT</span>
            <span data-testid={`node-tput-${data.label}`} className="node-tput">
              {tput}
            </span>
          </div>
        </div>
      </div>
      <Handle type="source" position={Position.Right} />
    </div>
  );
});
