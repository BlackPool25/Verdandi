// Shared topology types. T4 owns this module.
export const NODE_KINDS = ["machine", "sbuf", "c7tail"] as const;
export type NodeKind = (typeof NODE_KINDS)[number];

export const EDGE_CLASSES = [
  "line-gap",
  "tail-stage",
  "agv-drain",
  "assembly",
  "rework",
] as const;
export type EdgeClass = (typeof EDGE_CLASSES)[number];

// Extends Record<string, unknown>: seam required by @xyflow/react Node<T>.
export interface MachineNodeDatum extends Record<string, unknown> {
  readonly label: string;
  readonly kind: NodeKind;
  /** Live per-tick fields, patched via updateNodeData (T10 wires the stream). */
  readonly state?: string;
  readonly tput?: number;
  readonly obs?: number;
  /**
   * T9-owned anomaly overlay (additive: absent = plain node). Patched via
   * updateNodeData from anomalyFor(); TopologyView layout untouched.
   */
  readonly anomaly?: AnomalyDatum;
}

/** T9 anomaly overlay datum: GT outline, depth-1 neighbor, DOWN kind. */
export interface AnomalyDatum {
  readonly gt: boolean;
  readonly neighbor: boolean;
  readonly down: "natural" | "injected" | null;
  readonly faultId?: string | null;
}

export interface TopoEdgeDatum {
  readonly label: string;
  readonly edgeClass: EdgeClass;
  /** True for the rework back-edge that closes the ASM2→RWK0→ASM0 cycle. */
  readonly backEdge?: boolean;
}
