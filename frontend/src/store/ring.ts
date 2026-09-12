export class Ring {
  readonly buf: Float32Array;
  head = 0;
  count = 0;

  constructor(cap: number) {
    if (!Number.isInteger(cap) || cap <= 0) throw new RangeError("cap must be positive");
    this.buf = new Float32Array(cap);
  }

  get cap(): number {
    return this.buf.length;
  }

  get length(): number {
    return Math.min(this.count, this.buf.length);
  }

  push(v: number): void {
    this.buf[this.head] = v;
    this.head = (this.head + 1) % this.buf.length;
    this.count += 1;
  }

  snapshot(): Float32Array {
    const n = this.length;
    const out = new Float32Array(n);
    const start = (this.head - n + this.buf.length * 2) % this.buf.length;
    for (let i = 0; i < n; i += 1) {
      const cell = this.buf[(start + i) % this.buf.length];
      out[i] = cell === undefined ? NaN : cell;
    }
    return out;
  }
}

export function decimateMinMax(src: Float32Array, width: number): Float32Array {
  if (width <= 0) throw new RangeError("width must be positive");
  if (src.length <= width) return src.slice();
  const out = new Float32Array(width * 2);
  const per = src.length / width;
  for (let x = 0; x < width; x += 1) {
    const lo = Math.floor(x * per);
    const hi = Math.max(lo + 1, Math.floor((x + 1) * per));
    let mn = Infinity;
    let mx = -Infinity;
    for (let i = lo; i < hi && i < src.length; i += 1) {
      const v = src[i];
      if (v === undefined) continue;
      if (v < mn) mn = v;
      if (v > mx) mx = v;
    }
    out[x * 2] = mn === Infinity ? NaN : mn;
    out[x * 2 + 1] = mx === -Infinity ? NaN : mx;
  }
  return out;
}
