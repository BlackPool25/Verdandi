export interface StripCtx {
  clearRect(x: number, y: number, w: number, h: number): void;
  beginPath(): void;
  moveTo(x: number, y: number): void;
  lineTo(x: number, y: number): void;
  stroke(): void;
  readonly strokeStyle: string | CanvasGradient | CanvasPattern;
}

export interface Viewport {
  readonly w: number;
  readonly h: number;
}

export interface PaintSpec extends Viewport {
  readonly data: Float32Array;
  readonly min: number;
  readonly max: number;
  readonly stride: number;
}

export function paintStrip(ctx: StripCtx, spec: PaintSpec): number {
  const w = spec.w;
  const h = spec.h;
  ctx.clearRect(0, 0, w, h);
  const n = spec.data.length;
  if (n === 0 || w <= 0 || h <= 0) return 0;
  const span = spec.max - spec.min || 1;
  const stride = Math.max(1, spec.stride);
  ctx.beginPath();
  let segs = 0;
  let x = 0;
  for (let i = 0; i < n && x < w; i += stride, x += 1) {
    const v = spec.data[i];
    if (v === undefined || !Number.isFinite(v)) continue;
    const y = h - ((v - spec.min) / span) * h;
    if (segs === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
    segs += 1;
  }
  if (segs > 0) ctx.stroke();
  return segs;
}

export interface MinMaxSpec extends Viewport {
  readonly pairs: Float32Array;
  readonly min: number;
  readonly max: number;
  readonly totalSteps?: number | undefined;
}

export function paintMinMax(ctx: StripCtx, spec: MinMaxSpec): number {
  const pairs = spec.pairs;
  const min = spec.min;
  const max = spec.max;
  const w = spec.w;
  const h = spec.h;
  const total = spec.totalSteps ?? 300;
  ctx.clearRect(0, 0, w, h);
  if (pairs.length === 0 || w <= 0 || h <= 0) return 0;
  const span = max - min || 1;

  if (pairs.length >= w * 2) {
    const cols = Math.floor(pairs.length / 2);
    ctx.beginPath();
    let segs = 0;
    for (let x = 0; x < cols && x < w; x += 1) {
      const lo = pairs[x * 2];
      const hi = pairs[x * 2 + 1];
      if (lo === undefined || hi === undefined) continue;
      if (!Number.isFinite(lo) || !Number.isFinite(hi)) continue;
      const y1 = Math.max(0, Math.min(h, h - ((lo - min) / span) * h));
      const y2 = Math.max(0, Math.min(h, h - ((hi - min) / span) * h));
      ctx.moveTo(x, y1);
      ctx.lineTo(x, y2);
      segs += 1;
    }
    if (segs > 0) ctx.stroke();
    return segs;
  }

  ctx.beginPath();
  let segs = 0;
  for (let i = 0; i < pairs.length; i += 1) {
    const v = pairs[i];
    if (v === undefined || !Number.isFinite(v)) continue;
    const x = Math.min(w, (i / Math.max(1, total - 1)) * w);
    const y = Math.max(0, Math.min(h, h - ((v - min) / span) * h));
    if (segs === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
    segs += 1;
  }
  if (segs > 0) ctx.stroke();
  return segs;
}
