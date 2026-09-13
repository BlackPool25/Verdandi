import { BUFFER_IDS, MACHINE_IDS } from "../store/tick";
import type { Tick } from "../store/tick";

export function mulberry32(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const BASE = 50;
const AMP = 12;

export function buildBurst(n: number, seed = 777): Tick[] {
  const rand = mulberry32(seed);
  const phase = MACHINE_IDS.map(() => rand() * Math.PI * 2);
  const noise = MACHINE_IDS.map(() => 2 + rand() * 4);
  const out: Tick[] = [];
  for (let k = 0; k < n; k += 1) {
    const obs = MACHINE_IDS.map((_, i) => {
      const p = phase[i] ?? 0;
      const nz = noise[i] ?? 3;
      return BASE + AMP * Math.sin(k / 18 + p) + (rand() - 0.5) * nz;
    });
    const states = MACHINE_IDS.map((_, i) => (k % 97 === (i * 7) % 97 ? "DOWN" : "RUN"));
    const throughput = MACHINE_IDS.map((_, i) => ((k + i) % 11 === 0 ? 0 : 1));
    const buffers = BUFFER_IDS.map((id, i) =>
      id === "SBUF" ? 8 + ((k * 3 + i) % 20) : (k * 2 + i * 5) % 25,
    );
    const quality: Record<string, unknown> = {};
    for (const m of MACHINE_IDS) {
      quality[m] =
        k % 5 === 0
          ? { source: "parts-last", flag: k % 25 === 0 ? "DEGRADE" : "OK", part_id: `p${k}` }
          : "no completed part yet";
    }
    out.push({
      step: k,
      states,
      obs,
      throughput,
      buffers,
      sbuf_level: 8 + ((k * 3) % 20),
      events_at_k: [],
      faults: [],
      quality,
    });
  }
  return out;
}

export function faultStormBurst(n: number): Tick[] {
  const ticks = buildBurst(n, 777);
  return ticks.map((t, k) => ({
    ...t,
    states: MACHINE_IDS.map((_, i) => ((i + k) % 3 === 0 ? "DOWN" : "RUN")),
    events_at_k:
      k % 2 === 0
        ? [
            {
              event: "DOWN",
              t: k,
              machine: MACHINE_IDS[k % MACHINE_IDS.length],
              detail: "storm",
              natural: false,
              gt_excluded: false,
              fault_id: `storm-${k}`,
            },
          ]
        : [],
  }));
}
