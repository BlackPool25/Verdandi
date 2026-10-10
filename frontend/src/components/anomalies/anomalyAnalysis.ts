import { STREAM_MACHINE_ORDER } from "../../sim/streamCodec";
import type { FaultSpec, TwinEvent } from "../events/types";
import { PIPELINE_MACHINE_ORDER } from "../kpi/KpiStrip";
import { MACHINE_META } from "../panels/machineMeta";

export type AnomalyCategory =
  | "mechanical"
  | "sensor_drift"
  | "sensor_bias"
  | "process_delay"
  | "material_loss"
  | "quality_defect"
  | "logistics_wait";

export interface IncidentEvent {
  readonly id: string;
  readonly step: number;
  readonly machine: string;
  readonly type: "natural" | "injected" | "operational";
  readonly category: AnomalyCategory;
  readonly categoryLabel: string;
  readonly detail: string;
}

export interface SensorAnomaly {
  readonly step: number;
  readonly machine: string;
  readonly obs: number;
  readonly base: number;
  readonly sigma: number;
  readonly deviationSigma: number;
}

export interface EpisodeAnomalySummary {
  readonly totalSteps: number;
  readonly totalMachineTicks: number;
  readonly runTicks: number;
  readonly starvedTicks: number;
  readonly blockedTicks: number;
  readonly downTicks: number;
  readonly downRatePct: number;
  readonly starvedRatePct: number;
  readonly blockedRatePct: number;
  readonly disruptionRatePct: number;
  readonly availabilityPct: number;
  readonly incidents: readonly IncidentEvent[];
  readonly naturalBreakdownCount: number;
  readonly injectedFaultCount: number;
  readonly mechanicalWearCount: number;
  readonly sensorDriftCount: number;
  readonly sensorBiasCount: number;
  readonly processDelayCount: number;
  readonly qualityDefectCount: number;
  readonly materialLossCount: number;
  readonly logisticsWaitCount: number;
  readonly sensorAnomalyCount: number;
  readonly injectedAnomalyRatePct: number;
  readonly sensorAnomalies: readonly SensorAnomaly[];
  readonly sensorAnomalyRatePct: number;
  // Matrix ordered by PIPELINE_MACHINE_ORDER: [machineIdx][stepIdx] -> state
  readonly stateMatrix: readonly (readonly string[])[];
  // Mapping from PIPELINE_MACHINE_ORDER ID to its index in stateMatrix
  readonly machineList: readonly string[];
}

export function computeEpisodeAnomalies(
  rowCount: number,
  rowJson: (step: number) => string | undefined,
  headerFaults: readonly unknown[] = [],
): EpisodeAnomalySummary {
  const stepsToAnalyze = Math.min(300, rowCount);
  const totalMachineTicks = stepsToAnalyze * 26;

  let runTicks = 0;
  let starvedTicks = 0;
  let blockedTicks = 0;
  let downTicks = 0;

  const incidents: IncidentEvent[] = [];
  const sensorAnomalies: SensorAnomaly[] = [];

  // Initialize state matrix: 26 rows (PIPELINE_MACHINE_ORDER), stepsToAnalyze columns
  const matrix: string[][] = PIPELINE_MACHINE_ORDER.map(() =>
    new Array<string>(stepsToAnalyze).fill("IDLE"),
  );

  // Map machine ID to index in matrix
  const pipelineIndex = new Map<string, number>();
  PIPELINE_MACHINE_ORDER.forEach((id, idx) => pipelineIndex.set(id, idx));

  const seenIncidentKeys = new Set<string>();

  for (let k = 0; k < stepsToAnalyze; k++) {
    const raw = rowJson(k);
    if (!raw) continue;
    let data: any;
    try {
      data = JSON.parse(raw);
    } catch {
      continue;
    }

    const states: string[] = Array.isArray(data.states) ? data.states : [];
    const faults: FaultSpec[] = Array.isArray(data.faults) ? data.faults : [];
    const events: TwinEvent[] = Array.isArray(data.events_at_k) ? data.events_at_k : [];

    // Analyze machine states
    STREAM_MACHINE_ORDER.forEach((machId, streamIdx) => {
      const state = states[streamIdx] ?? "IDLE";
      const pIdx = pipelineIndex.get(machId);
      if (pIdx !== undefined && matrix[pIdx]) {
        matrix[pIdx][k] = state;
      }

      if (state === "RUN") runTicks++;
      else if (state === "STARVED") starvedTicks++;
      else if (state === "BLOCKED") blockedTicks++;
      else if (state === "DOWN") downTicks++;
    });

    // Check events across all anomaly families
    for (const e of events) {
      if (e.event === "DOWN") {
        const rawEvent = e as unknown as Record<string, unknown>;
        const detail = (e.detail && typeof e.detail === "object" ? e.detail : {}) as Record<string, unknown>;
        const isNatural = Boolean(
          rawEvent["natural"] === true ||
          detail["natural"] === true ||
          rawEvent["gt_excluded"] === true ||
          detail["gt_excluded"] === true
        );
        const key = `DOWN_${e.machine}_${k}`;
        if (!seenIncidentKeys.has(key)) {
          seenIncidentKeys.add(key);
          incidents.push({
            id: `NAT-${e.machine}-t${k}`,
            step: k,
            machine: e.machine,
            type: isNatural ? "natural" : "injected",
            category: "mechanical",
            categoryLabel: isNatural ? "MECHANICAL WEAR (MTTF)" : "INJECTED BREAKDOWN",
            detail: isNatural
              ? `Natural mechanical component wear on ${e.machine} (Poisson MTTF). Downstream impact: material starvation.`
              : `Injected downtime fault on ${e.machine}.`,
          });
        }
      } else if (e.event === "FAULT_START") {
        const detail = (e.detail && typeof e.detail === "object" ? e.detail : {}) as Record<string, unknown>;
        const fCls = String(detail["class"] ?? detail["fault_class"] ?? "drift").toLowerCase();
        const key = `FAULT_START_${e.machine}_${k}`;
        if (!seenIncidentKeys.has(key)) {
          seenIncidentKeys.add(key);
          let cat: AnomalyCategory = "sensor_drift";
          let label = "SENSOR DRIFT";
          let desc = `Injected sensor calibration drift on ${e.machine}.`;

          if (fCls === "bias" || fCls === "spike") {
            cat = "sensor_bias";
            label = "SENSOR BIAS";
            desc = `Injected sensor offset bias on ${e.machine}.`;
          } else if (fCls === "delay") {
            cat = "process_delay";
            label = "PROCESS DELAY";
            desc = `Injected cycle time delay on ${e.machine}.`;
          } else if (fCls === "loss") {
            cat = "material_loss";
            label = "MATERIAL LOSS";
            desc = `Injected yield/part loss on ${e.machine}.`;
          } else if (fCls === "quality") {
            cat = "quality_defect";
            label = "QUALITY DEFECT";
            desc = `Injected quality defect on ${e.machine}. Assemblies diverted to RWK0.`;
          } else if (fCls === "breakdown" || fCls === "stuck") {
            cat = "mechanical";
            label = "INJECTED BREAKDOWN";
            desc = `Injected machine breakdown stoppage on ${e.machine}.`;
          }

          incidents.push({
            id: String(detail["fault_id"] ?? `F-${e.machine}-t${k}`),
            step: k,
            machine: e.machine,
            type: "injected",
            category: cat,
            categoryLabel: label,
            detail: desc,
          });
        }
      } else if (e.event === "REJECT_ROUTE") {
        const key = `REJECT_${e.machine}_${k}`;
        if (!seenIncidentKeys.has(key)) {
          seenIncidentKeys.add(key);
          const detail = (e.detail && typeof e.detail === "object" ? e.detail : {}) as Record<string, unknown>;
          const target = String(detail["to"] ?? "RWK0");
          incidents.push({
            id: `REJ-${e.machine}-t${k}`,
            step: k,
            machine: e.machine,
            type: "operational",
            category: "quality_defect",
            categoryLabel: "QUALITY REJECT & REWORK",
            detail: `Inspection out-of-tolerance defect on ${e.machine}. Part routed to ${target} Rework Bay.`,
          });
        }
      } else if (e.event === "AGV_WAIT") {
        const key = `AGV_WAIT_${e.machine}_${Math.floor(k / 5)}`;
        if (!seenIncidentKeys.has(key)) {
          seenIncidentKeys.add(key);
          const detail = (e.detail && typeof e.detail === "object" ? e.detail : {}) as Record<string, unknown>;
          const waitTime = Number(detail["wait"] ?? 0);
          const holdTime = Number(detail["hold"] ?? 0);
          incidents.push({
            id: `AGV-${e.machine}-t${k}`,
            step: k,
            machine: e.machine,
            type: "operational",
            category: "logistics_wait",
            categoryLabel: "LOGISTICS AGV WAIT",
            detail: `AGV transport corridor contention at tail buffer ${e.machine} (wait: ${waitTime} steps, hold: ${holdTime} steps). Downstream Assembly ASM0 kit arrival delayed.`,
          });
        }
      } else if (e.event === "LATE_VERDICT") {
        const key = `LATE_VERDICT_${e.machine}_${k}`;
        if (!seenIncidentKeys.has(key)) {
          seenIncidentKeys.add(key);
          const detail = (e.detail && typeof e.detail === "object" ? e.detail : {}) as Record<string, unknown>;
          const verdict = String(detail["verdict"] ?? "DEGRADE");
          const partId = Number(detail["part"] ?? 0);
          incidents.push({
            id: `VERDICT-${e.machine}-t${k}`,
            step: k,
            machine: e.machine,
            type: "operational",
            category: "quality_defect",
            categoryLabel: "QUALITY INSPECTION VERDICT",
            detail: `Quality inspection verdict at test station ${e.machine}: verdict=${verdict} for workpiece #${partId}.`,
          });
        }
      } else if (e.event === "DIVERT_SBUF") {
        const key = `DIVERT_SBUF_${e.machine}_${k}`;
        if (!seenIncidentKeys.has(key)) {
          seenIncidentKeys.add(key);
          incidents.push({
            id: `DIVERT-${e.machine}-t${k}`,
            step: k,
            machine: e.machine,
            type: "operational",
            category: "logistics_wait",
            categoryLabel: "BUFFER OVERFLOW (SBUF)",
            detail: `Line buffer full on ${e.machine}. In-flight workpiece diverted to SBUF emergency overflow storage.`,
          });
        }
      }
    }

    // Continuous statistical sensor anomaly detection (>3σ outlier check across 26 channels)
    if (Array.isArray(data.obs)) {
      STREAM_MACHINE_ORDER.forEach((machId, streamIdx) => {
        const meta = MACHINE_META[machId];
        if (!meta) return;
        const val = Number(data.obs[streamIdx]);
        if (!Number.isFinite(val)) return;

        const dev = Math.abs(val - meta.base);
        const z = dev / meta.sigma;
        if (z >= 3.0) {
          sensorAnomalies.push({
            step: k,
            machine: machId,
            obs: Number(val.toFixed(2)),
            base: meta.base,
            sigma: meta.sigma,
            deviationSigma: Number(z.toFixed(2)),
          });

          // Debounce incident ledger: 1 incident per machine per 10-step window
          const sensorKey = `SENSOR_OUTLIER_${machId}_${Math.floor(k / 10)}`;
          if (!seenIncidentKeys.has(sensorKey)) {
            seenIncidentKeys.add(sensorKey);
            incidents.push({
              id: `SIG-${machId}-t${k}`,
              step: k,
              machine: machId,
              type: "operational",
              category: "sensor_drift",
              categoryLabel: "STATISTICAL SENSOR OUTLIER (>3σ)",
              detail: `Sensor telemetry (${val.toFixed(2)}) deviated by ${z.toFixed(1)}σ from nominal baseline (${meta.base.toFixed(1)} ± ${meta.sigma.toFixed(1)}).`,
            });
          }
        }
      });
    }

    // Check active injected faults
    for (const f of faults) {
      if (f && typeof f === "object" && "origin" in f && "t0" in f) {
        const origin = String(f.origin);
        const t0 = Number(f.t0);
        if (k === t0) {
          const key = `FAULT_${f.id ?? origin}_${t0}`;
          if (!seenIncidentKeys.has(key)) {
            seenIncidentKeys.add(key);
            const fCls = String(f.class ?? "drift").toLowerCase();
            let cat: AnomalyCategory = "sensor_drift";
            let label = "SENSOR DRIFT";
            if (fCls === "bias" || fCls === "spike") {
              cat = "sensor_bias";
              label = "SENSOR BIAS";
            } else if (fCls === "delay") {
              cat = "process_delay";
              label = "PROCESS DELAY";
            } else if (fCls === "loss") {
              cat = "material_loss";
              label = "MATERIAL LOSS";
            } else if (fCls === "quality") {
              cat = "quality_defect";
              label = "QUALITY DEFECT";
            } else if (fCls === "breakdown" || fCls === "stuck") {
              cat = "mechanical";
              label = "INJECTED BREAKDOWN";
            }

            incidents.push({
              id: f.id ?? `F-${origin}-t${t0}`,
              step: t0,
              machine: origin,
              type: "injected",
              category: cat,
              categoryLabel: label,
              detail: `Injected ${fCls} anomaly on ${origin} (dur: ${f.dur ?? "?"} steps)`,
            });
          }
        }
      }
    }
  }

  // Also check header faults if any were defined but not yet seen
  for (const hf of headerFaults) {
    if (hf && typeof hf === "object" && "origin" in hf && "t0" in hf) {
      const f = hf as FaultSpec;
      const key = `FAULT_${f.id ?? f.origin}_${f.t0}`;
      if (!seenIncidentKeys.has(key)) {
        seenIncidentKeys.add(key);
        const fCls = String(f.class ?? "drift").toLowerCase();
        let cat: AnomalyCategory = "sensor_drift";
        let label = "SENSOR DRIFT";
        if (fCls === "bias" || fCls === "spike") {
          cat = "sensor_bias";
          label = "SENSOR BIAS";
        } else if (fCls === "delay") {
          cat = "process_delay";
          label = "PROCESS DELAY";
        } else if (fCls === "loss") {
          cat = "material_loss";
          label = "MATERIAL LOSS";
        } else if (fCls === "quality") {
          cat = "quality_defect";
          label = "QUALITY DEFECT";
        } else if (fCls === "breakdown" || fCls === "stuck") {
          cat = "mechanical";
          label = "INJECTED BREAKDOWN";
        }

        incidents.push({
          id: f.id ?? `F-${f.origin}-t${f.t0}`,
          step: Number(f.t0),
          machine: String(f.origin),
          type: "injected",
          category: cat,
          categoryLabel: label,
          detail: `Injected ${fCls} anomaly (dur: ${f.dur ?? "?"} steps)`,
        });
      }
    }
  }

  // Sort incidents chronologically by step
  incidents.sort((a, b) => a.step - b.step);

  const naturalBreakdownCount = incidents.filter((i) => i.type === "natural").length;
  const injectedFaultCount = incidents.filter((i) => i.type === "injected").length;
  const mechanicalWearCount = incidents.filter((i) => i.category === "mechanical" && i.type === "natural").length;
  const sensorDriftCount = incidents.filter((i) => i.category === "sensor_drift").length;
  const sensorBiasCount = incidents.filter((i) => i.category === "sensor_bias").length;
  const processDelayCount = incidents.filter((i) => i.category === "process_delay").length;
  const qualityDefectCount = incidents.filter((i) => i.category === "quality_defect").length;
  const materialLossCount = incidents.filter((i) => i.category === "material_loss").length;
  const logisticsWaitCount = incidents.filter((i) => i.category === "logistics_wait").length;
  const sensorAnomalyCount = sensorAnomalies.length;

  const downRatePct = totalMachineTicks > 0 ? (downTicks / totalMachineTicks) * 100 : 0;
  const starvedRatePct = totalMachineTicks > 0 ? (starvedTicks / totalMachineTicks) * 100 : 0;
  const blockedRatePct = totalMachineTicks > 0 ? (blockedTicks / totalMachineTicks) * 100 : 0;
  const disruptionRatePct =
    totalMachineTicks > 0 ? ((downTicks + starvedTicks + blockedTicks) / totalMachineTicks) * 100 : 0;
  const availabilityPct = totalMachineTicks > 0 ? (runTicks / totalMachineTicks) * 100 : 0;
  const injectedAnomalyRatePct =
    totalMachineTicks > 0 ? (injectedFaultCount / totalMachineTicks) * 100 : 0;
  const sensorAnomalyRatePct =
    totalMachineTicks > 0 ? (sensorAnomalyCount / totalMachineTicks) * 100 : 0;

  return {
    totalSteps: stepsToAnalyze,
    totalMachineTicks,
    runTicks,
    starvedTicks,
    blockedTicks,
    downTicks,
    downRatePct: Number(downRatePct.toFixed(2)),
    starvedRatePct: Number(starvedRatePct.toFixed(2)),
    blockedRatePct: Number(blockedRatePct.toFixed(2)),
    disruptionRatePct: Number(disruptionRatePct.toFixed(2)),
    availabilityPct: Number(availabilityPct.toFixed(2)),
    incidents,
    naturalBreakdownCount,
    injectedFaultCount,
    mechanicalWearCount,
    sensorDriftCount,
    sensorBiasCount,
    processDelayCount,
    qualityDefectCount,
    materialLossCount,
    logisticsWaitCount,
    sensorAnomalyCount,
    injectedAnomalyRatePct: Number(injectedAnomalyRatePct.toFixed(2)),
    sensorAnomalies,
    sensorAnomalyRatePct: Number(sensorAnomalyRatePct.toFixed(2)),
    stateMatrix: matrix,
    machineList: PIPELINE_MACHINE_ORDER,
  };
}
