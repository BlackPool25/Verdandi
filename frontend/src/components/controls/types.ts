export const T_TOTAL = 300;
export const MAX_STEP = T_TOTAL - 1;
export const CAL_WIN = 120;
export const STEPS_PER_SEC_AT_1X = 4;
export const SPEEDS: readonly number[] = [1, 2, 4];
export const QUALITY_HOME = "ASM2";

export const MACHINES: readonly string[] = [
  "A0", "A1", "A2", "A3", "A4", "A5", "A6", "A7", "A8", "A9",
  "B0", "B1", "B2", "B3", "B4", "B5", "B6", "B7", "B8", "B9",
  "C0", "C1", "C2", "C3", "C4", "C5", "C6", "C7",
  "ASM0", "ASM1", "ASM2", "RWK0",
];

export const FAULT_CLASSES: readonly string[] = [
  "drift",
  "bias",
  "delay",
  "loss",
  "breakdown",
  "quality",
  "spike",
];

export const STUCK_LABEL = "STUCK";
export const NORMALIZED_STUCK = "breakdown";
export const FAULT_CLASS_OPTIONS: readonly string[] = [...FAULT_CLASSES, STUCK_LABEL];

export interface FaultDraft {
  id: string;
  faultClass: string;
  origin: string;
  t0: number;
  dur: number;
  extra: Record<string, number>;
}

export interface NormalizedFault {
  id: string;
  class: string;
  origin: string;
  t0: number;
  dur: number;
  mag_sigma: number | null;
  extra: Record<string, unknown>;
}

export interface EpisodeCreated {
  episode_id: string;
  seed: number;
  faults: NormalizedFault[];
  enable_natural_breakdown: boolean;
  noop_warning: boolean;
  replay_digest: string;
}

export interface TickRow {
  step: number;
  [key: string]: unknown;
}

export const VALIDATION_HINTS =
  "t0 ≥ 120 · t0+dur ≤ 300 · same-machine gap ≥ 5 steps · dur 8–25 · " +
  "mag 4–7σ · delay d 3–6 · drop 0.10–0.30 · mttr_mult 1–3 · " +
  "reject 0.15–0.40 · STUCK → breakdown · quality outside ASM2 = noop";

export const EXTRA_HINTS: Record<string, string> = {
  drift: "extra: {} or {mag_sigma} — mag 4–7σ (top-level mag_sigma also accepted)",
  bias: "extra: {} or {mag_sigma} — mag 4–7σ (top-level mag_sigma also accepted)",
  spike: "extra: {} or {mag_sigma} — mag 4–7σ (top-level mag_sigma also accepted)",
  delay: 'extra: {} or {"d": 3–6}',
  loss: 'extra: {} or {"drop_rate": 0.10–0.30}',
  breakdown: 'extra: {} or {"mttr_mult": 1–3}',
  quality: 'extra: {} or {"reject_rate": 0.15–0.40} — only ASM2 takes effect',
  STUCK: 'STUCK normalizes to breakdown; extra: {} or {"mttr_mult": 1–3}',
};
