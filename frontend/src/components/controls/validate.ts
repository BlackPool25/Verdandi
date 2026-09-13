import {
  CAL_WIN,
  FAULT_CLASSES,
  MACHINES,
  NORMALIZED_STUCK,
  STUCK_LABEL,
  T_TOTAL,
  type FaultDraft,
} from "./types";

const ALLOWED = new Set<string>([...FAULT_CLASSES, STUCK_LABEL]);

function normalizeClass(cls: string): string {
  return cls === STUCK_LABEL ? NORMALIZED_STUCK : cls;
}

export function validateSeed(seed: unknown): string | null {
  if (typeof seed === "boolean" || typeof seed !== "number" || !Number.isInteger(seed) || seed < 0) {
    return `seed must be a non-negative int, got ${JSON.stringify(seed)}`;
  }
  return null;
}

export function validateFaults(faults: readonly FaultDraft[]): string[] {
  const errors: string[] = [];
  for (const f of faults) {
    if (!MACHINES.includes(f.origin)) {
      errors.push(`unknown fault origin ${JSON.stringify(f.origin)}`);
    }
    if (!ALLOWED.has(f.faultClass)) {
      errors.push(`unknown fault class ${JSON.stringify(f.faultClass)}`);
    }
    if (!Number.isInteger(f.t0) || !Number.isInteger(f.dur) || f.t0 < CAL_WIN || f.dur < 1 || f.t0 + f.dur > T_TOTAL) {
      errors.push(
        `fault window out of range: t0=${JSON.stringify(f.t0)} dur=${JSON.stringify(f.dur)} ` +
          `(need t0>=CAL_WIN, dur>=1, t0+dur<=T)`,
      );
    }
    if (f.dur < 8 || f.dur > 25) {
      errors.push(`bridge-strict (superset of twin): fault ${f.id}: dur=${JSON.stringify(f.dur)} out of range [8,25]`);
    }
    const cls = normalizeClass(f.faultClass);
    const extra = f.extra;
    if (cls === "delay" && "d" in extra) {
      const d = extra["d"];
      if (!Number.isInteger(d) || d < 3 || d > 6) {
        errors.push(`bridge-strict (superset of twin): fault ${f.id}: d=${JSON.stringify(d)} out of range [3,6]`);
      }
    }
    if (cls === "loss" && "drop_rate" in extra) {
      const v = extra["drop_rate"];
      if (typeof v !== "number" || v < 0.1 || v > 0.3) {
        errors.push(
          `bridge-strict (superset of twin): fault ${f.id}: drop_rate=${JSON.stringify(v)} out of range [0.1,0.3]`,
        );
      }
    }
    if (cls === "breakdown" && "mttr_mult" in extra) {
      const v = extra["mttr_mult"];
      if (typeof v !== "number" || v < 1 || v > 3) {
        errors.push(
          `bridge-strict (superset of twin): fault ${f.id}: mttr_mult=${JSON.stringify(v)} out of range [1,3]`,
        );
      }
    }
    if (cls === "quality" && "reject_rate" in extra) {
      const v = extra["reject_rate"];
      if (typeof v !== "number" || v < 0.15 || v > 0.4) {
        errors.push(
          `bridge-strict (superset of twin): fault ${f.id}: reject_rate=${JSON.stringify(v)} out of range [0.15,0.4]`,
        );
      }
    }
  }
  const byMachine = new Map<string, FaultDraft[]>();
  for (const f of faults) {
    const list = byMachine.get(f.origin) ?? [];
    list.push(f);
    byMachine.set(f.origin, list);
  }
  for (const windows of byMachine.values()) {
    if (windows.length < 2) continue;
    const ordered = [...windows].sort((a, b) => a.t0 - b.t0);
    for (let i = 0; i + 1 < ordered.length; i++) {
      const a = ordered[i];
      const b = ordered[i + 1];
      if (a !== undefined && b !== undefined && b.t0 - (a.t0 + a.dur) < 5) {
        errors.push(
          `same-machine fault windows overlap or gap<5: ${a.id} [${a.t0},${a.t0 + a.dur}) vs ${b.id} [${b.t0},${b.t0 + b.dur})`,
        );
      }
    }
  }
  return errors;
}

export function clientWarnings(seedText: string, faults: readonly FaultDraft[]): string[] {
  const errors: string[] = [];
  const seed = seedText.trim() === "" ? Number.NaN : Number(seedText);
  const seedErr = validateSeed(seed);
  if (seedErr !== null) errors.push(seedErr);
  errors.push(...validateFaults(faults));
  return errors;
}
