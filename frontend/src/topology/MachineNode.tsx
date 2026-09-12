import { memo } from "react";
import type { Node, NodeProps } from "@xyflow/react";
import { Handle, Position } from "@xyflow/react";
import "../components/events/events.css";
import type { MachineNodeDatum } from "./types";

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
  return (
    <div
      data-testid={`node-${data.label}`}
      data-state={data.state ?? "unknown"}
      data-gt={anomaly?.gt === true ? "true" : "false"}
      data-down={anomaly?.down ?? ""}
      data-neighbor={anomaly?.neighbor === true ? "true" : "false"}
      className={overlayClass === "" ? undefined : overlayClass}
      style={{
        width: 120,
        height: 60,
        border: "1px solid #888",
        background: "#111",
        color: "#eee",
        fontSize: 12,
      }}
    >
      <Handle type="target" position={Position.Left} />
      <div>
        {data.label}
        {glyph}
      </div>
      <div data-testid={`node-state-${data.label}`}>{data.state ?? "—"}</div>
      <Handle type="source" position={Position.Right} />
    </div>
  );
});
