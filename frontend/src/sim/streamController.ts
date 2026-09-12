import {
  BYTE_BUDGET,
  T_TOTAL,
  parseLiveTick,
  streamUrl,
  type OpenStream,
  type StreamHandle,
} from "./streamCodec";

export interface ControllerOptions {
  readonly reconnectDelayMs?: number;
  readonly onLog?: (msg: string) => void;
}

// Framework-free lifecycle controller (unit-tested via injected OpenStream).
// Single-stream invariant: connect() always closes the previous handle first.
// Speed is cursor-only: setSpeed never reconnects, never moves the cursor.
// Resume is idempotent: reconnect() re-requests from the last received step
// and row overwrites keep resumed rows byte-identical to the original run.
export class TickStreamController {
  private readonly open: OpenStream;
  private readonly delayMs: number;
  private readonly log: (msg: string) => void;
  private handle: StreamHandle | null = null;
  private url = "";
  private episode: string | null = null;
  private readonly rows = new Map<number, string>();
  private c7tail: number | null = null;
  private lastStep = -1;
  private bytes = 0;
  private speedVal = 1;
  private reconnectFlag = false;
  private timer: ReturnType<typeof setTimeout> | null = null;
  private readonly subs = new Set<() => void>();
  private baseVal = "";

  constructor(open: OpenStream, opts: ControllerOptions = {}) {
    this.open = open;
    this.delayMs = opts.reconnectDelayMs ?? 500;
    this.log = opts.onLog ?? ((m: string) => console.info(m));
  }

  subscribe(fn: () => void): () => void {
    this.subs.add(fn);
    return () => {
      this.subs.delete(fn);
    };
  }

  private emit(): void {
    for (const fn of [...this.subs]) fn();
  }

  private closeHandle(): void {
    this.handle?.close();
    this.handle = null;
  }

  private clearTimer(): void {
    if (this.timer !== null) {
      clearTimeout(this.timer);
      this.timer = null;
    }
  }

  connect(episodeId: string, base = ""): void {
    this.closeHandle();
    this.clearTimer();
    if (this.episode !== episodeId) {
      this.episode = episodeId;
      this.rows.clear();
      this.c7tail = null;
      this.lastStep = -1;
      this.bytes = 0;
      this.reconnectFlag = false;
    }
    this.baseVal = base;
    const from = this.lastStep > 0 ? this.lastStep : 0;
    this.url = streamUrl(base, episodeId, from);
    const src = this.open(this.url);
    this.handle = src;
    this.attach(src);
    this.emit();
  }

  private scheduleResume(): void {
    this.clearTimer();
    this.timer = setTimeout(() => {
      this.timer = null;
      if (this.episode === null || this.complete() || this.handle === null) return;
      const id = this.episode;
      const base = this.baseVal;
      this.closeHandle();
      this.clearTimer();
      this.baseVal = base;
      this.url = streamUrl(base, id, this.lastStep > 0 ? this.lastStep : 0);
      const src = this.open(this.url);
      this.handle = src;
      this.attach(src);
      this.emit();
    }, this.delayMs);
  }

  private attach(src: StreamHandle): void {
    src.addEventListener("header", (ev) => {
      this.bytes += ev.data.length;
      try {
        const body: unknown = JSON.parse(ev.data);
        if (typeof body === "object" && body !== null && "c7tail_final" in body) {
          const v = (body as { readonly c7tail_final?: unknown }).c7tail_final;
          if (typeof v === "number" && Number.isFinite(v)) this.c7tail = v;
        }
      } catch {
        /* header without finals: panels show the no-episode state */
      }
      this.reconnectFlag = false;
      this.emit();
    });
    src.addEventListener("tick", (ev) => {
      let data: unknown = null;
      try {
        data = JSON.parse(ev.data) as unknown;
      } catch {
        return;
      }
      const row = parseLiveTick(data);
      if (row === null) return;
      this.bytes += ev.data.length;
      this.rows.set(row.step, ev.data);
      if (row.step > this.lastStep) this.lastStep = row.step;
      this.reconnectFlag = false;
      if (this.rowCount() === T_TOTAL) {
        this.log(
          `[tickSource] episode ${this.episode} complete: rows=${this.rowCount()} bytes=${this.bytes} budget_ok=${this.byteBudgetOk()}`,
        );
      }
      this.emit();
    });
    src.addEventListener("error", () => {
      if (this.complete() || this.handle === null) {
        this.reconnectFlag = false;
        this.emit();
        return;
      }
      this.reconnectFlag = true;
      this.emit();
      this.scheduleResume();
    });
    src.addEventListener("open", () => {
      this.reconnectFlag = false;
      this.emit();
    });
  }

  disconnect(): void {
    this.clearTimer();
    this.closeHandle();
    this.reconnectFlag = false;
    this.emit();
  }

  reconnect(): void {
    if (this.episode === null) return;
    this.connect(this.episode, this.baseVal);
  }

  setSpeed(s: number): void {
    if (Number.isFinite(s) && s > 0) this.speedVal = s;
    this.emit();
  }

  cursor(): number {
    return this.lastStep;
  }

  rowCount(): number {
    return this.rows.size;
  }

  rowJson(step: number): string | undefined {
    return this.rows.get(step);
  }

  c7tailFinal(): number | null {
    return this.c7tail;
  }

  totalBytes(): number {
    return this.bytes;
  }

  byteBudgetOk(): boolean {
    return this.bytes < BYTE_BUDGET;
  }

  complete(): boolean {
    if (this.rows.size !== T_TOTAL) return false;
    for (let k = 0; k < T_TOTAL; k += 1) {
      if (!this.rows.has(k)) return false;
    }
    return true;
  }

  reconnecting(): boolean {
    return this.reconnectFlag;
  }

  episodeId(): string | null {
    return this.episode;
  }

  speed(): number {
    return this.speedVal;
  }
}
