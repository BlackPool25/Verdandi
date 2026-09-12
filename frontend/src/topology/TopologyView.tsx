import { useCallback, useEffect, useMemo } from "react";
import {
  ReactFlow,
  ReactFlowProvider,
  useNodesState,
  useReactFlow,
  type Edge,
  type Node,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { EXPECTED_EDGE_COUNT, PINNED_EDGES } from "./edges";
import { computeLayout } from "./layout";
import { MachineNode } from "./MachineNode";
import { anomalyFor } from "../components/events/anomaly";
import type { FaultSpec } from "../components/events/types";
import { EXPECTED_NODE_COUNT, PINNED_NODES } from "./nodes";
import type { MachineNodeDatum } from "./types";

const nodeTypes = { machine: MachineNode };

// Frozen tick shape (subset T4 needs): 9-key schema vectors by machine id.
// Full Tick type lives in sim/tickSource; TopologyView only consumes states.
export interface TickPatch {
  readonly step: number;
  readonly states: Readonly<Record<string, string>>;
  readonly tput: Readonly<Record<string, number>>;
}

interface TopologyViewProps {
  readonly tick: TickPatch | null;
  readonly connected: boolean;
  readonly faults?: readonly FaultSpec[] | undefined;
  readonly onRetry?: (() => void) | undefined;
}

export function TopologyView(props: TopologyViewProps): React.JSX.Element {
  return (
    <ReactFlowProvider>
      <TopologyInner tick={props.tick} connected={props.connected} faults={props.faults} onRetry={props.onRetry} />
    </ReactFlowProvider>
  );
}

function TopologyInner({ tick, connected, faults, onRetry }: TopologyViewProps): React.JSX.Element {
  const { updateNodeData } = useReactFlow();

  // Layout precomputed on topology change only (empty deps: pinned roster).
  const { initialNodes, initialEdges } = useMemo(() => {
    const laid = computeLayout(PINNED_NODES, PINNED_EDGES);
    const pos = new Map(laid.map((n) => [n.id, n] as const));
    const initialNodes: Node[] = PINNED_NODES.map((n) => {
      const p = pos.get(n.id);
      return {
        id: n.id,
        type: "machine",
        position: { x: p?.x ?? 0, y: p?.y ?? 0 },
        data: { ...n.data } satisfies MachineNodeDatum,
      };
    });
    const initialEdges: Edge[] = PINNED_EDGES.map((e) => ({
      id: e.id,
      source: e.source,
      target: e.target,
      label: e.data.label,
    }));
    if (initialNodes.length !== EXPECTED_NODE_COUNT) {
      throw new Error(`node drift: ${initialNodes.length}`);
    }
    if (initialEdges.length !== EXPECTED_EDGE_COUNT) {
      throw new Error(`edge drift: ${initialEdges.length}`);
    }
    return { initialNodes, initialEdges };
  }, []);

  const [nodes, , onNodesChange] = useNodesState(initialNodes);

  const onConnect = useCallback(() => undefined, []);

  // Per-tick path: updateNodeData patches datum in place, no re-layout.
  // Anomaly overlay rides the same patch (absent faults = plain node).
  useEffect(() => {
    if (tick === null) return;
    const specs = faults ?? [];
    for (const [id, state] of Object.entries(tick.states)) {
      updateNodeData(id, {
        state,
        tput: tick.tput[id] ?? 0,
        anomaly: anomalyFor(id, tick.step, specs, tick.states),
      });
    }
  }, [tick, faults, updateNodeData]);

  return (
    <div style={{ width: "100%", height: "100vh" }} data-testid="topology">
      {!connected && (
        <div data-testid="disconnected-banner" role="alert">
          Bridge disconnected — showing last layout, no live ticks.{" "}
          {onRetry !== undefined && (
            <button type="button" data-testid="banner-retry" onClick={onRetry}>
              Retry
            </button>
          )}
        </div>
      )}
      <ReactFlow
        nodes={nodes}
        edges={initialEdges}
        nodeTypes={nodeTypes}
        onNodesChange={onNodesChange}
        onConnect={onConnect}
        onlyRenderVisibleElements
        fitView
        fitViewOptions={{ padding: 0.25, minZoom: 0.1 }}
      />
    </div>
  );
}
