// Shared topology types. T4 owns this module.
export const NODE_KINDS = ["machine", "sbuf", "c7tail"] as const;
export type NodeKind = (typeof NODE_KINDS)[number];

export const EDGE_CLASSES = [
  "line-gap",
  "tail-stage",
  "agv-drain",
  "assembly",
  "rework",
  "packaging",
] as const;
export type EdgeClass = (typeof EDGE_CLASSES)[number];

export const SPRITE_CLASSES = [
  "feed",
  "form",
  "process",
  "finish",
  "inspect-tail",
  "assembly-kit",
  "assembly-join",
  "test",
  "rework",
] as const;
export type SpriteClass = (typeof SPRITE_CLASSES)[number];
export type SpriteId = `sprite-${SpriteClass}`;
export const SPRITE_FALLBACK: SpriteId = "sprite-process";

const SPRITE_IDS: Readonly<Record<string, SpriteId>> = {
  feed: "sprite-feed",
  form: "sprite-form",
  process: "sprite-process",
  finish: "sprite-finish",
  "inspect-tail": "sprite-inspect-tail",
  "assembly-kit": "sprite-assembly-kit",
  "assembly-join": "sprite-assembly-join",
  test: "sprite-test",
  rework: "sprite-rework",
};

export function spriteFor(cls: string): SpriteId {
  return SPRITE_IDS[cls] ?? SPRITE_FALLBACK;
}

// Extends Record<string, unknown>: seam required by @xyflow/react Node<T>.
export interface MachineNodeDatum extends Record<string, unknown> {
  readonly label: string;
  readonly kind: NodeKind;
  /**
   * T1 sprite contract: cls mirrors MACHINE_META cls verbatim; spriteId is
   * `sprite-${cls}` via spriteFor(). Absent = unresolved (patched per-tick).
   */
  readonly cls?: SpriteClass;
  readonly spriteId?: SpriteId;
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
