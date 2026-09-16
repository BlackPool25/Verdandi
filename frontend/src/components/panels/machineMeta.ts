// T8 machine roster mirror — values mechanically dumped from src/config.py (Table 3.1).
// Do NOT hand-edit; regenerate from config. c7tail/SBUF are stores, not machines.

export interface MachineMeta { readonly cls: string; readonly base: number; readonly sigma: number; readonly cycle: number; readonly mttf: number; readonly mttr: number; readonly bufferCap: number | null; }

export const MACHINE_META: Readonly<Record<string, MachineMeta>> = {
  A0: { cls: "feed", base: 50.0, sigma: 1.0, cycle: 4, mttf: 2000, mttr: 15, bufferCap: 20 },
  A1: { cls: "form", base: 60.0, sigma: 1.2, cycle: 5, mttf: 1500, mttr: 12, bufferCap: 20 },
  A2: { cls: "process", base: 70.0, sigma: 1.5, cycle: 6, mttf: 800, mttr: 20, bufferCap: 25 },
  A7: { cls: "process", base: 70.0, sigma: 1.5, cycle: 6, mttf: 800, mttr: 20, bufferCap: 25 },
  A8: { cls: "finish", base: 55.0, sigma: 1.1, cycle: 4, mttf: 1200, mttr: 10, bufferCap: 15 },
  A9: { cls: "inspect-tail", base: 48.0, sigma: 1.4, cycle: 3, mttf: 1500, mttr: 8, bufferCap: 15 },
  B0: { cls: "feed", base: 50.0, sigma: 1.0, cycle: 4, mttf: 2000, mttr: 15, bufferCap: 20 },
  B1: { cls: "form", base: 60.0, sigma: 1.2, cycle: 5, mttf: 1500, mttr: 12, bufferCap: 20 },
  B2: { cls: "process", base: 70.0, sigma: 1.5, cycle: 6, mttf: 800, mttr: 20, bufferCap: 25 },
  B7P: { cls: "process", base: 70.0, sigma: 1.5, cycle: 6, mttf: 800, mttr: 20, bufferCap: 25 },
  B7S: { cls: "process", base: 70.0, sigma: 1.5, cycle: 6, mttf: 800, mttr: 20, bufferCap: 25 },
  B8: { cls: "finish", base: 55.0, sigma: 1.1, cycle: 4, mttf: 1200, mttr: 10, bufferCap: 15 },
  B9: { cls: "inspect-tail", base: 48.0, sigma: 1.4, cycle: 3, mttf: 1500, mttr: 8, bufferCap: 15 },
  C0: { cls: "feed", base: 50.0, sigma: 1.0, cycle: 4, mttf: 2000, mttr: 15, bufferCap: 20 },
  C1: { cls: "form", base: 60.0, sigma: 1.2, cycle: 5, mttf: 1500, mttr: 12, bufferCap: 20 },
  C2: { cls: "process", base: 70.0, sigma: 1.5, cycle: 6, mttf: 800, mttr: 20, bufferCap: 25 },
  C6: { cls: "process", base: 70.0, sigma: 1.5, cycle: 6, mttf: 800, mttr: 20, bufferCap: 25 },
  C7: { cls: "inspect-tail", base: 48.0, sigma: 1.4, cycle: 3, mttf: 1500, mttr: 8, bufferCap: 15 },
  PKG0: { cls: "assembly-kit", base: 65.0, sigma: 1.3, cycle: 5, mttf: 1000, mttr: 12, bufferCap: 25 },
  PKG1: { cls: "finish", base: 55.0, sigma: 1.1, cycle: 4, mttf: 1200, mttr: 10, bufferCap: 15 },
  PKG2: { cls: "finish", base: 55.0, sigma: 1.1, cycle: 4, mttf: 1200, mttr: 10, bufferCap: 15 },
  ASM0: { cls: "assembly-kit", base: 65.0, sigma: 1.3, cycle: 5, mttf: 1000, mttr: 12, bufferCap: 25 },
  ASM1: { cls: "assembly-join", base: 66.0, sigma: 1.3, cycle: 6, mttf: 1000, mttr: 12, bufferCap: 25 },
  INSP0: { cls: "test", base: 45.0, sigma: 2.0, cycle: 2, mttf: 1200, mttr: 10, bufferCap: 25 },
  ASM2: { cls: "test", base: 45.0, sigma: 2.0, cycle: 3, mttf: 1200, mttr: 10, bufferCap: null },
  RWK0: { cls: "rework", base: 62.0, sigma: 1.6, cycle: 8, mttf: 900, mttr: 18, bufferCap: 10 },
};

export const BUFFER_CAPS: Readonly<Record<string, number>> = {
  A01: 20,
  A12: 20,
  A27: 25,
  A78: 15,
  A89: 15,
  B01: 20,
  B12: 20,
  B2B7P: 25,
  B2B7S: 25,
  B7PB8: 25,
  B7SB8: 25,
  B89: 15,
  C01: 20,
  C12: 20,
  C26: 25,
  C67: 15,
  ASM01: 25,
  INSP01: 25,
  INSP02: 25,
  GA9: 15,
  GB9: 15,
  C7PKG: 15,
  PKG01: 15,
  PKG02: 15,
  RWK_RET: 10,
  SBUF: 30,
};

export const SBUF_CAP = 30;
export const SBUF_HIGH = 24.0; // >=80% of cap (twin _SBUF_HIGH)
export const TAILS: readonly string[] = ["A9", "B9", "C7", "PKG1", "PKG2"];
export const NEVER_DIVERT_CLASSES: readonly string[] = ["feed", "form"]; // SBUF guard: process/finish/inspect-tail divert, feed/form never
export const AGV_STEPS: readonly [number, number] = [4, 8];
