// FE-11 shared step-gap contract: seek/transport holes must render as an
// explicit gap state (break line + badge) instead of a continuous chart
// over discontinuous data. Both StripChart and EventFeed consume this
// module; the only input is the played-step sequence (or NaN runs in a
// series), so sparse-but-normal data never flags without a step signal.

/** Present steps `from` and `to` with every step between them missing. */
export interface StepGap {
  readonly from: number;
  readonly to: number;
}

/** Inclusive index run of missing (non-finite) samples in a series. */
export interface MissingRun {
  readonly start: number;
  readonly end: number;
}

/**
 * Holes in a played-step sequence: consecutive sorted steps differing by
 * more than 1. Tolerant of unsorted input and duplicates; ignores
 * non-integer or negative entries.
 */
export function findStepGaps(steps: readonly number[]): StepGap[] {
  const uniq = [...new Set(steps)].filter(
    (s) => Number.isInteger(s) && s >= 0,
  );
  uniq.sort((a, b) => a - b);
  const gaps: StepGap[] = [];
  for (let i = 1; i < uniq.length; i += 1) {
    const prev = uniq[i - 1];
    const cur = uniq[i];
    if (prev === undefined || cur === undefined) continue;
    if (cur - prev > 1) gaps.push({ from: prev, to: cur });
  }
  return gaps;
}

/** Missing-step count for one gap (always >= 1). */
export function missingStepCount(gap: StepGap): number {
  return Math.max(1, gap.to - gap.from - 1);
}

/** Human range for one gap: "step 4" or "steps 2–3". */
export function gapRangeLabel(gap: StepGap): string {
  const missing = missingStepCount(gap);
  return missing === 1 ? `step ${gap.from + 1}` : `steps ${gap.from + 1}–${gap.to - 1}`;
}

/** Compact badge summary: "" | "steps 3–4" | "steps 1–2; steps 5–8". */
export function summarizeStepGaps(gaps: readonly StepGap[], maxRanges = 3): string {
  const shown = gaps.slice(0, Math.max(1, maxRanges)).map(gapRangeLabel);
  const extra = gaps.length - shown.length;
  return extra > 0 ? `${shown.join("; ")}; +${extra} more` : shown.join("; ");
}

/**
 * Inclusive runs of non-finite samples (NaN/Infinity) in a dense series.
 * The missing-data sentinel path for charts rendered without a step list.
 */
export function findMissingRuns(values: ArrayLike<number>): MissingRun[] {
  const runs: MissingRun[] = [];
  let start = -1;
  for (let i = 0; i < values.length; i += 1) {
    const v = values[i];
    if (v === undefined || !Number.isFinite(v)) {
      if (start < 0) start = i;
    } else if (start >= 0) {
      runs.push({ start, end: i - 1 });
      start = -1;
    }
  }
  if (start >= 0) runs.push({ start, end: values.length - 1 });
  return runs;
}

/** Human range for one missing run: "step 4" or "steps 2–5". */
export function missingRunLabel(run: MissingRun): string {
  return run.start === run.end ? `step ${run.start}` : `steps ${run.start}–${run.end}`;
}
