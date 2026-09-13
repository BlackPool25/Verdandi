import { MAX_STEP, STEPS_PER_SEC_AT_1X } from "./types";

export function clampStep(n: number): number {
  if (!Number.isFinite(n)) return 0;
  return Math.min(MAX_STEP, Math.max(0, Math.floor(n)));
}

export function stepBy(step: number, delta: number): number {
  return clampStep(step + delta);
}

export function intervalMs(speed: number): number {
  return 1000 / (STEPS_PER_SEC_AT_1X * speed);
}
