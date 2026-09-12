import { createStore } from "zustand/vanilla";
import type { BufferId, MachineId, Tick } from "./tick";
import { BUFFER_IDS, MACHINE_IDS } from "./tick";
import { Ring } from "./ring";

export type Listener = () => void;
export type Unsub = () => void;

export interface BadgeSnapshot {
  readonly cursor: number;
  readonly sbufLevel: number;
  readonly backpressure: number;
  readonly updatedAt: number;
}

export interface TwinStoreOptions {
  readonly cap?: number;
  readonly frameBudget?: number;
  readonly badgeIntervalMs?: number;
  readonly machineOrder?: readonly string[];
  readonly bufferOrder?: readonly string[];
  readonly now?: () => number;
  readonly onPaint?: (painted: readonly string[]) => void;
}

const DEFAULT_CAP = 1200;
const DEFAULT_FRAME_BUDGET = 8;
const DEFAULT_BADGE_MS = 100;

export interface TwinStore {
  ingest(tick: Tick): void;
  subscribeTransient(fn: Listener): Unsub;
  subscribeBadges(fn: Listener): Unsub;
  flushBadges(): void;
  paintDirty(): void;
  cursor(): number;
  backpressure(): number;
  paintCount(): number;
  badges(): BadgeSnapshot;
  series(id: MachineId | string): Float32Array;
  bufferSeries(id: BufferId | string): Float32Array;
  reset(): void;
}

export function createTwinStore(opts: TwinStoreOptions = {}): TwinStore {
  const cap = opts.cap ?? DEFAULT_CAP;
  const frameBudget = opts.frameBudget ?? DEFAULT_FRAME_BUDGET;
  const badgeMs = opts.badgeIntervalMs ?? DEFAULT_BADGE_MS;
  const now = opts.now ?? Date.now;
  const onPaint = opts.onPaint;
  const mOrder = opts.machineOrder ?? MACHINE_IDS;
  const bOrder = opts.bufferOrder ?? BUFFER_IDS;

  const obsRings = new Map<string, Ring>();
  const bufRings = new Map<string, Ring>();
  for (const id of mOrder) obsRings.set(id, new Ring(cap));
  for (const id of bOrder) bufRings.set(id, new Ring(cap));

  // T12: the React-observed badge snapshot lives in a zustand/vanilla store
  // (one per createTwinStore call). subscribeBadges delegates to the vanilla
  // subscribe; per-tick fan-out stays a transient emitter (never setState per
  // tick), which is exactly the zustand transient-update pattern.
  const badgeStore = createStore<BadgeSnapshot>()(() => ({
    cursor: -1,
    sbufLevel: 0,
    backpressure: 0,
    updatedAt: 0,
  }));

  const tickListeners = new Set<Listener>();
  const dirty = new Set<string>();
  let cursor = -1;
  let ticksSincePaint = 0;
  let dropped = 0;
  let paints = 0;
  let lastBadgeAt = Number.NEGATIVE_INFINITY;
  let lastSbuf = 0;

  function emit(set: Set<Listener>): void {
    for (const fn of [...set]) fn();
  }

  return {
    ingest(tick: Tick): void {
      const n = Math.min(tick.obs.length, mOrder.length);
      for (let i = 0; i < n; i += 1) {
        const id = mOrder[i];
        const v = tick.obs[i];
        if (id === undefined || v === undefined) continue;
        const ring = obsRings.get(id);
        if (ring === undefined) continue;
        ring.push(v);
        dirty.add(id);
      }
      const m = Math.min(tick.buffers.length, bOrder.length);
      for (let i = 0; i < m; i += 1) {
        const id = bOrder[i];
        const v = tick.buffers[i];
        if (id === undefined || v === undefined) continue;
        const ring = bufRings.get(id);
        if (ring === undefined) continue;
        ring.push(v);
        dirty.add(`buf:${id}`);
      }
      cursor = tick.step;
      lastSbuf = tick.sbuf_level;
      ticksSincePaint += 1;
      emit(tickListeners);
    },

    subscribeTransient(fn: Listener): Unsub {
      tickListeners.add(fn);
      return () => {
        tickListeners.delete(fn);
      };
    },

    subscribeBadges(fn: Listener): Unsub {
      return badgeStore.subscribe(fn);
    },

    flushBadges(): void {
      const t = now();
      if (t - lastBadgeAt < badgeMs) return;
      lastBadgeAt = t;
      badgeStore.setState({ cursor, sbufLevel: lastSbuf, backpressure: dropped, updatedAt: t });
    },

    paintDirty(): void {
      if (ticksSincePaint > frameBudget) dropped += ticksSincePaint - frameBudget;
      const painted = [...dirty];
      dirty.clear();
      ticksSincePaint = 0;
      paints += 1;
      if (onPaint !== undefined && painted.length > 0) onPaint(painted);
    },

    cursor(): number {
      return cursor;
    },

    backpressure(): number {
      return dropped;
    },

    paintCount(): number {
      return paints;
    },

    badges(): BadgeSnapshot {
      return badgeStore.getState();
    },

    series(id: MachineId | string): Float32Array {
      return obsRings.get(id)?.snapshot() ?? new Float32Array(0);
    },

    bufferSeries(id: BufferId | string): Float32Array {
      return bufRings.get(id)?.snapshot() ?? new Float32Array(0);
    },

    reset(): void {
      for (const r of obsRings.values()) {
        r.head = 0;
        r.count = 0;
      }
      for (const r of bufRings.values()) {
        r.head = 0;
        r.count = 0;
      }
      dirty.clear();
      cursor = -1;
      ticksSincePaint = 0;
      dropped = 0;
      paints = 0;
      lastBadgeAt = Number.NEGATIVE_INFINITY;
      badgeStore.setState({ cursor: -1, sbufLevel: 0, backpressure: 0, updatedAt: 0 });
    },
  };
}
