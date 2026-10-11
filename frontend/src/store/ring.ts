// Ring buffer – used as a step-indexed flat array (cap >> T_TOTAL=300).
// `set(step, v)` writes at buf[step] directly; `snapshot(limit)` returns
// buf[0..limit] so scrubbing backward just passes a smaller limit and the
// graph automatically trims to the playhead position.
// `push` appends in order (step 0,1,2,…) and is kept for compatibility.
export class Ring {
  readonly buf: Float32Array;
  head = 0;   // next write index for push()
  count = 0;  // number of slots written via push() or set()

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

  /** Append the next value (streaming forward playback). */
  push(v: number): void {
    const idx = this.head;
    if (idx >= this.buf.length) return; // full
    this.buf[idx] = v;
    this.head = idx + 1;
    this.count = this.head;
  }

  /** Write a specific step slot directly (supports out-of-order ingest). */
  set(step: number, v: number): void {
    if (step < 0 || step >= this.buf.length) return;
    this.buf[step] = v;
    if (step + 1 > this.count) {
      this.count = step + 1;
      this.head = this.count;
    }
  }

  /**
   * Return buf[0..limit-1] (or all written slots if limit is undefined).
   * Because data is stored at buf[step], limiting to `step+1` entries gives
   * exactly the history up to that playback position.
   */
  snapshot(limit?: number): Float32Array {
    const n = this.length;
    const targetLen = limit === undefined ? n : Math.max(0, Math.min(n, limit));
    return this.buf.slice(0, targetLen);
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
