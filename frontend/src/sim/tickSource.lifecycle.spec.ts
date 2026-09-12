import { describe, expect, it } from "vitest";
import {
  BYTE_BUDGET,
  STREAM_MACHINE_ORDER,
  T_TOTAL,
  TickStreamController,
  parseLiveTick,
  streamUrl,
  toPatch,
  type LiveTick,
  type OpenStream,
  type StreamHandle,
} from "./tickSource";

// Failing-first lifecycle spec (T10): disconnect/resume, backpressure,
// multispeed, episode switch, byte budget, 300/300 guarantee.

const EP = "ep-1";

function mkTick(step: number): LiveTick {
  return {
    step,
    states: Array.from({ length: 32 }, () => "RUN"),
    throughput: Array.from({ length: 32 }, () => 1),
  };
}

type FrameListener = (ev: { readonly data: string }) => void;

class FakeSource implements StreamHandle {
  static instances: FakeSource[] = [];
  readonly url: string;
  closed = false;
  private readonly listeners = new Map<string, FrameListener[]>();

  constructor(url: string) {
    this.url = url;
    FakeSource.instances.push(this);
  }

  addEventListener(type: string, fn: FrameListener): void {
    const arr = this.listeners.get(type) ?? [];
    arr.push(fn);
    this.listeners.set(type, arr);
  }

  emit(type: string, data: string): void {
    for (const fn of this.listeners.get(type) ?? []) fn({ data });
  }

  close(): void {
    this.closed = true;
  }
}

function harness(delayMs = 0): { ctrl: TickStreamController; open: OpenStream } {
  FakeSource.instances = [];
  const open: OpenStream = (url: string) => new FakeSource(url);
  const ctrl = new TickStreamController(open, { reconnectDelayMs: delayMs });
  return { ctrl, open };
}

function live(): FakeSource {
  const cur = FakeSource.instances[FakeSource.instances.length - 1];
  if (cur === undefined) throw new Error("no live source");
  return cur;
}

function feedTicks(src: FakeSource, from: number, to: number): string[] {
  const raws: string[] = [];
  for (let k = from; k <= to; k += 1) {
    const raw = JSON.stringify(mkTick(k));
    raws.push(raw);
    src.emit("tick", raw);
  }
  return raws;
}

const flush = (): Promise<void> => new Promise((r) => setTimeout(r, 0));

describe("streamUrl", () => {
  it("starts without from_step; resumes with ?from_step=k", () => {
    expect(streamUrl("", EP)).toBe(`/stream?episode_id=${EP}`);
    expect(streamUrl("", EP, 150)).toBe(`/stream?episode_id=${EP}&from_step=150`);
  });
});

describe("single stream invariant", () => {
  it("episode switch closes the old source; only one stays open", () => {
    const { ctrl } = harness();
    ctrl.connect(EP);
    const first = live();
    ctrl.connect("ep-2");
    const second = live();
    expect(first.closed).toBe(true);
    expect(second.closed).toBe(false);
    expect(FakeSource.instances.filter((s) => !s.closed)).toHaveLength(1);
    expect(ctrl.episodeId()).toBe("ep-2");
  });
});

describe("disconnect at k=150 → resume identical", () => {
  it("reconnects with from_step=150 and resumed rows match the original", async () => {
    const { ctrl } = harness();
    ctrl.connect(EP);
    const s1 = live();
    feedTicks(s1, 0, 150);
    expect(ctrl.cursor()).toBe(150);
    ctrl.disconnect();
    expect(s1.closed).toBe(true);

    ctrl.reconnect();
    await flush();
    const s2 = live();
    expect(s2.url).toBe(`/stream?episode_id=${EP}&from_step=150`);

    // Reference full run built independently (same deterministic factory).
    const reference = new Map<number, string>();
    for (let k = 0; k < T_TOTAL; k += 1) reference.set(k, JSON.stringify(mkTick(k)));

    feedTicks(s2, 150, 299);
    expect(ctrl.rowCount()).toBe(T_TOTAL);
    expect(ctrl.complete()).toBe(true);
    for (let k = 150; k < T_TOTAL; k += 1) {
      expect(ctrl.rowJson(k)).toBe(reference.get(k));
    }
  });
});

describe("speed change keeps cursor", () => {
  it("setSpeed never reconnects and never moves the cursor", () => {
    const { ctrl } = harness();
    ctrl.connect(EP);
    const s1 = live();
    feedTicks(s1, 0, 40);
    ctrl.setSpeed(4);
    expect(FakeSource.instances).toHaveLength(1);
    expect(live()).toBe(s1);
    expect(ctrl.cursor()).toBe(40);
    expect(ctrl.speed()).toBe(4);
  });
});

describe("byte budget", () => {
  it("accounts every tick payload byte and stays under 2MB", () => {
    const { ctrl } = harness();
    ctrl.connect(EP);
    const raws = feedTicks(live(), 0, 299);
    const expected = raws.reduce((n, r) => n + r.length, 0);
    expect(ctrl.totalBytes()).toBe(expected);
    expect(ctrl.totalBytes()).toBeLessThan(BYTE_BUDGET);
    expect(ctrl.byteBudgetOk()).toBe(true);
  });
});

describe("300/300 guarantee", () => {
  it("complete only when every step 0..299 is present", () => {
    const { ctrl } = harness();
    ctrl.connect(EP);
    feedTicks(live(), 0, 298);
    expect(ctrl.rowCount()).toBe(299);
    expect(ctrl.complete()).toBe(false);
    live().emit("tick", JSON.stringify(mkTick(299)));
    expect(ctrl.complete()).toBe(true);
  });
});

describe("error → reconnect banner → resume", () => {
  it("streams error flags reconnecting and auto-resumes from cursor", async () => {
    const { ctrl } = harness();
    ctrl.connect(EP);
    feedTicks(live(), 0, 60);
    expect(ctrl.reconnecting()).toBe(false);
    live().emit("error", "");
    expect(ctrl.reconnecting()).toBe(true);
    await flush();
    const s2 = live();
    expect(s2.url).toBe(`/stream?episode_id=${EP}&from_step=60`);
    s2.emit("open", "");
    expect(ctrl.reconnecting()).toBe(false);
  });

  it("no reconnect once the episode is complete", async () => {
    const { ctrl } = harness();
    ctrl.connect(EP);
    feedTicks(live(), 0, 299);
    const n = FakeSource.instances.length;
    live().emit("error", "");
    await flush();
    expect(FakeSource.instances).toHaveLength(n);
    expect(ctrl.reconnecting()).toBe(false);
  });
});

describe("robustness", () => {
  it("malformed tick frames are ignored; cursor stays put", () => {
    const { ctrl } = harness();
    ctrl.connect(EP);
    feedTicks(live(), 0, 10);
    live().emit("tick", "{not json");
    live().emit("tick", JSON.stringify({ step: "x", states: [], throughput: [] }));
    expect(ctrl.cursor()).toBe(10);
    expect(ctrl.rowCount()).toBe(11);
  });
});

describe("wire order + patch mapping", () => {
  it("STREAM_MACHINE_ORDER is the sorted 32-id roster the bridge replays", () => {
    expect(STREAM_MACHINE_ORDER).toHaveLength(32);
    expect([...STREAM_MACHINE_ORDER].sort()).toEqual([...STREAM_MACHINE_ORDER]);
    expect(STREAM_MACHINE_ORDER).toContain("ASM0");
    expect(STREAM_MACHINE_ORDER).toContain("RWK0");
    expect(STREAM_MACHINE_ORDER.indexOf("ASM0")).toBe(10);
  });

  it("toPatch maps arrays by wire order; parseLiveTick rejects bad rows", () => {
    const row = mkTick(7);
    const patch = toPatch(row, STREAM_MACHINE_ORDER);
    expect(patch.step).toBe(7);
    expect(patch.states["ASM0"]).toBe("RUN");
    expect(patch.tput["RWK0"]).toBe(1);
    expect(parseLiveTick({ step: 1, states: [], throughput: [] })).toBeNull();
    expect(parseLiveTick(row)).not.toBeNull();
  });
});
