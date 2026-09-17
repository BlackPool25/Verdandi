import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Background,
  BackgroundVariant,
  ReactFlow,
  ReactFlowProvider,
  useNodesState,
  useReactFlow,
  useViewport,
  type Edge,
  type Node,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { PINNED_EDGES, bufferIdForEdge, widthForUtil } from "./edges";
import { NODE_HEIGHT, NODE_WIDTH, computeLayout, type RankDir } from "./layout";
import { MachineNode } from "./MachineNode";
import { anomalyFor } from "../components/events/anomaly";
import type { FaultSpec } from "../components/events/types";
import { PINNED_NODES, assertTopologyCounts } from "./nodes";
import type { MachineNodeDatum } from "./types";
import { bufferBarsFor, type PanelTick } from "../components/panels/selectors";

const nodeTypes = { machine: MachineNode };

// Frozen tick shape (subset T4 needs): 9-key schema vectors by machine id.
// Full Tick type lives in sim/tickSource; TopologyView only consumes states.
export interface TickPatch {
  readonly step: number;
  readonly states: Readonly<Record<string, string>>;
  readonly tput: Readonly<Record<string, number>>;
  readonly buffers?: Readonly<Record<string, number>> | undefined;
}

interface TopologyViewProps {
  readonly tick: TickPatch | null;
  readonly connected: boolean;
  readonly faults?: readonly FaultSpec[] | undefined;
  readonly onRetry?: (() => void) | undefined;
  readonly selectedId?: string | null | undefined;
  readonly onSelect?: ((id: string) => void) | undefined;
  readonly panelTick?: PanelTick | null | undefined;
}

export function TopologyView(props: TopologyViewProps): React.JSX.Element {
  return (
    <ReactFlowProvider>
      <TopologyInner
        tick={props.tick}
        connected={props.connected}
        faults={props.faults}
        onRetry={props.onRetry}
        selectedId={props.selectedId}
        onSelect={props.onSelect}
        panelTick={props.panelTick}
      />
    </ReactFlowProvider>
  );
}

function TopologyInner({
  tick,
  connected,
  faults,
  onRetry,
  selectedId,
  onSelect,
  panelTick,
}: TopologyViewProps): React.JSX.Element {
  const { updateNodeData, fitView, setCenter } = useReactFlow();
  const [direction, setDirection] = useState<RankDir>("FLOOR");

  // Dagre re-layout on direction toggle ONLY (never per tick). Positions
  // recompute; node data is untouched (setNodes maps positions, see below).
  const layoutPos = useMemo(
    () => computeLayout(PINNED_NODES, PINNED_EDGES, undefined, direction),
    [direction],
  );

  // Base roster: layout positions + pinned datum, rebuilt on toggle only.
  const { baseNodes } = useMemo(() => {
    const pos = new Map(layoutPos.map((n) => [n.id, n] as const));
    const baseNodes: Node[] = PINNED_NODES.map((n) => {
      const p = pos.get(n.id);
      return {
        id: n.id,
        type: "machine",
        position: { x: p?.x ?? 0, y: p?.y ?? 0 },
        data: { ...n.data } satisfies MachineNodeDatum,
      };
    });
    assertTopologyCounts(baseNodes.length, PINNED_EDGES.length);
    return { baseNodes };
  }, [layoutPos]);

  const [nodes, setNodes, onNodesChange] = useNodesState(baseNodes);

  // Toggle path: new positions onto live nodes, data (state/tput/anomaly)
  // and selection spread through untouched.
  useEffect(() => {
    const pos = new Map(layoutPos.map((n) => [n.id, n] as const));
    setNodes((nds) =>
      nds.map((n) => {
        const p = pos.get(n.id);
        return p === undefined ? n : { ...n, position: { x: p.x, y: p.y } };
      }),
    );
  }, [layoutPos, setNodes]);

  // Selection path: flag-only patch, datum untouched (memo nodes keep
  // their per-tick identity; only the two flipped nodes re-render).
  useEffect(() => {
    setNodes((nds) =>
      nds.map((n) => {
        const want = n.id === selectedId;
        return n.selected === want ? n : { ...n, selected: want };
      }),
    );
  }, [selectedId, setNodes]);

  const onConnect = useCallback(() => undefined, []);

  // Edge widths track live buffer utilization (bufferBarsFor util 0..1 →
  // strokeWidth 1..4). Unmapped edges (stores/kitC) stay at 1. Back-edge
  // keeps its dashed class/style on every width. Edges never re-layout.
  const utilByBuffer = useMemo(() => {
    const m = new Map<string, number>();
    if (panelTick !== null && panelTick !== undefined) {
      for (const b of bufferBarsFor(panelTick)) m.set(b.id, b.util);
    }
    return m;
  }, [panelTick]);

  const edges: Edge[] = useMemo(
    () =>
      PINNED_EDGES.map((e) => {
        const buf = bufferIdForEdge(e);
        const w = buf === null ? 1 : widthForUtil(utilByBuffer.get(buf) ?? 0);
        const back = e.data.backEdge === true;
        return {
          id: e.id,
          source: e.source,
          target: e.target,
          label: e.data.label,
          data: { ...e.data },
          className:
            back === true ? `topo-edge ${e.data.edgeClass} back-edge` : `topo-edge ${e.data.edgeClass}`,
          style: back === true ? { strokeWidth: w, strokeDasharray: "6 4" } : { strokeWidth: w },
        };
      }),
    [utilByBuffer],
  );

  // Click-to-select: shared SimPage selection + zoom-to-node ~1.2.
  // Reduced-motion pins the zoom jump to duration 0 (no animation).
  const onNodeClick = useCallback(
    (_ev: React.MouseEvent, node: Node) => {
      onSelect?.(node.id);
      const reduce =
        typeof window !== "undefined" &&
        "matchMedia" in window &&
        window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      setCenter(node.position.x + NODE_WIDTH / 2, node.position.y + NODE_HEIGHT / 2, {
        zoom: 1.2,
        duration: reduce ? 0 : 300,
      });
    },
    [onSelect, setCenter],
  );

  const onToggleDirection = useCallback(() => {
    setDirection((d) => (d === "FLOOR" ? "LR" : d === "LR" ? "TB" : "FLOOR"));
  }, []);

  // Imperative re-fit after first paint: the fitView prop races initial
  // node measurement (edges/nodes mount async), so re-fit once on mount
  // to guarantee all 28 nodes / 31 edges are visible after fit.
  useEffect(() => {
    const raf = requestAnimationFrame(() => {
      void fitView({ padding: 0.25, minZoom: 0.1 });
    });
    return () => cancelAnimationFrame(raf);
  }, [fitView]);

  // Per-tick path: RAF-coalesced updateNodeData (T6 render throttle).
  // Last-write-wins: ticks arriving faster than a frame (4x = 62.5ms, still
  // >16ms, but burst catch-ups coalesce) keep only the latest patch.
  // If-changed guard: per-node flat signature skips nodes whose
  // state/tput/anomaly are identical, so unchanged nodes never re-render.
  // Datum stays small/flat ({state, tput, anomaly}); layout untouched.
  const pendingRef = useRef<TickPatch | null>(null);
  const rafRef = useRef<number>(0);
  const appliedRef = useRef<Map<string, string>>(new Map());
  const faultsRef = useRef(faults);
  faultsRef.current = faults;
  useEffect(() => {
    if (tick === null) return;
    pendingRef.current = tick;
    if (rafRef.current !== 0) return;
    rafRef.current = window.requestAnimationFrame(() => {
      rafRef.current = 0;
      const latest = pendingRef.current;
      pendingRef.current = null;
      if (latest === null) return;
      const specs = faultsRef.current ?? [];
      const applied = appliedRef.current;
      for (const [id, state] of Object.entries(latest.states)) {
        const tput = latest.tput[id] ?? 0;
        const anomaly = anomalyFor(id, latest.step, specs, latest.states);
        // Flat signature: anomaly is a small object or null; JSON is cheap
        // here vs a wasted updateNodeData + node re-render downstream.
        const sig = `${state}|${tput}|${anomaly === null || anomaly === undefined ? "" : JSON.stringify(anomaly)}`;
        if (applied.get(id) === sig) continue;
        applied.set(id, sig);
        updateNodeData(id, { state, tput, anomaly });
      }
    });
  }, [tick, faults, updateNodeData]);
  useEffect(
    () => () => {
      if (rafRef.current !== 0) window.cancelAnimationFrame(rafRef.current);
    },
    [],
  );

  return (
    <div style={{ width: "100%", minWidth: 320, height: "100vh", minHeight: 240 }} data-testid="topology">
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
      <button
        type="button"
        data-testid="direction-toggle"
        aria-pressed={direction === "TB"}
        onClick={onToggleDirection}
        className="px-btn topo-layout-btn"
      >
        Layout: {direction}
      </button>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodesChange={onNodesChange}
        onNodeClick={onNodeClick}
        onConnect={onConnect}
        onlyRenderVisibleElements={false}
        fitView
        fitViewOptions={{ padding: 0.25, minZoom: 0.1 }}
        minZoom={0.1}
      >
        <Background variant={BackgroundVariant.Dots} gap={24} size={1} color="#ded8cb" />
        <FloorPlanLayer direction={direction} />
      </ReactFlow>
    </div>
  );
}

function FloorPlanLayer({ direction }: { readonly direction: RankDir }): React.JSX.Element | null {
  const { x, y, zoom } = useViewport();
  if (direction !== "FLOOR") return null;

  return (
    <svg
      className="scada-floor-plan-svg"
      aria-hidden="true"
      style={{
        position: "absolute",
        top: 0,
        left: 0,
        width: "100%",
        height: "100%",
        pointerEvents: "none",
        zIndex: 0,
        overflow: "visible",
      }}
    >
      <g transform={`translate(${x}, ${y}) scale(${zoom})`}>
        {/* Line A: Machining Bay */}
        <rect x={40} y={60} width={1470} height={120} fill="#ede8dc" stroke="#b8b3a5" strokeWidth={1} strokeDasharray="4 4" rx={2} />
        <text x={50} y={78} fill="#2b303a" fontSize={11} fontFamily="var(--font-mono, monospace)" letterSpacing="1px" fontWeight="bold">
          BAY 01 // LINE A [MACHINING] (A0-A9)
        </text>

        {/* Line B: Process Bay */}
        <rect x={40} y={200} width={1470} height={120} fill="#ede8dc" stroke="#b8b3a5" strokeWidth={1} strokeDasharray="4 4" rx={2} />
        <text x={50} y={218} fill="#2b303a" fontSize={11} fontFamily="var(--font-mono, monospace)" letterSpacing="1px" fontWeight="bold">
          BAY 02 // LINE B [PROCESS] (B0-B9)
        </text>

        {/* Line C: Stamping Bay */}
        <rect x={180} y={340} width={1180} height={120} fill="#ede8dc" stroke="#b8b3a5" strokeWidth={1} strokeDasharray="4 4" rx={2} />
        <text x={190} y={358} fill="#2b303a" fontSize={11} fontFamily="var(--font-mono, monospace)" letterSpacing="1px" fontWeight="bold">
          BAY 03 // LINE C [STAMPING] (C1-C7)
        </text>

        {/* AGV Corridor & SBUF Logistics */}
        <rect x={1540} y={60} width={180} height={400} fill="#e5dfd2" stroke="#257179" strokeWidth={1} strokeDasharray="6 3" rx={2} />
        <text x={1550} y={78} fill="#1b4965" fontSize={10} fontFamily="var(--font-mono, monospace)" fontWeight="bold">
          AGV FLEET AISLE
        </text>
        <text x={1550} y={92} fill="#5e656e" fontSize={9} fontFamily="var(--font-mono, monospace)">
          TRANSIT: 3-5 STEPS
        </text>

        {/* Assembly Cell */}
        <rect x={1740} y={190} width={440} height={130} fill="#ede8dc" stroke="#b8b3a5" strokeWidth={1} strokeDasharray="4 4" rx={2} />
        <text x={1750} y={208} fill="#2b303a" fontSize={11} fontFamily="var(--font-mono, monospace)" letterSpacing="1px" fontWeight="bold">
          CELL 04 // FINAL ASSEMBLY (ASM0-2)
        </text>

        {/* Rework Bay */}
        <rect x={1880} y={340} width={200} height={110} fill="#f4ebd9" stroke="#c28e47" strokeWidth={1} strokeDasharray="4 2" rx={2} />
        <text x={1890} y={358} fill="#8c632b" fontSize={10} fontFamily="var(--font-mono, monospace)" fontWeight="bold">
          BAY 05 // REWORK (RWK0)
        </text>
      </g>
    </svg>
  );
}
