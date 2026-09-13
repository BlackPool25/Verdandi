import { useEffect, useRef } from "react";
import type { TwinStore } from "../../store/twinStore";
import { decimateMinMax } from "../../store/ring";
import { paintMinMax } from "./paintStrip";
import { useBadges } from "./useBadges";

export interface StripChartProps {
  readonly store: TwinStore;
  readonly machineId: string;
  readonly width?: number;
  readonly height?: number;
  readonly min?: number;
  readonly max?: number;
}

export function StripChart({
  store,
  machineId,
  width = 280,
  height = 64,
  min = 0,
  max = 100,
}: StripChartProps): React.JSX.Element {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const dirtyRef = useRef(false);
  const badges = useBadges(store);

  useEffect(() => {
    return store.subscribeTransient(() => {
      dirtyRef.current = true;
    });
  }, [store]);

  useEffect(() => {
    let raf = 0;
    const frame = (): void => {
      raf = requestAnimationFrame(frame);
      // Paint-only-when-dirty: idle frames do no canvas/store work.
      if (!dirtyRef.current) return;
      // Skip when tab hidden: keep dirty so the next visible frame repaints.
      if (typeof document !== "undefined" && document.hidden) return;
      const canvas = canvasRef.current;
      if (canvas === null) return;
      // Skip when hidden/collapsed: keep dirty so it repaints on show.
      if (!canvas.isConnected) return;
      const rect = canvas.getBoundingClientRect();
      if (rect.width === 0 || rect.height === 0) return;
      dirtyRef.current = false;
      const ctx = canvas.getContext("2d");
      if (ctx === null) return;
      // DPR-scale backing store; paint in CSS pixels.
      const dpr =
        typeof window !== "undefined" && Number.isFinite(window.devicePixelRatio)
          ? window.devicePixelRatio || 1
          : 1;
      const backingW = Math.max(1, Math.round(width * dpr));
      const backingH = Math.max(1, Math.round(height * dpr));
      if (canvas.width !== backingW || canvas.height !== backingH) {
        canvas.width = backingW;
        canvas.height = backingH;
      }
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      const data = store.series(machineId);
      const pairs = decimateMinMax(data, Math.max(1, Math.floor(width)));
      paintMinMax(ctx, { pairs, min, max, w: width, h: height });
      store.paintDirty();
    };
    raf = requestAnimationFrame(frame);
    return () => {
      cancelAnimationFrame(raf);
    };
  }, [store, machineId, width, height, min, max]);

  return (
    <figure data-testid={`strip-${machineId}`} aria-label={`${machineId} strip chart`}>
      <canvas
        ref={canvasRef}
        width={width}
        height={height}
        style={{ width, height, display: "block", maxWidth: "100%" }}
      />
      <figcaption>
        {badges.cursor < 0 ? (
          <span data-testid={`strip-empty-${machineId}`}>no data yet</span>
        ) : (
          <span>
            {machineId} · step {badges.cursor} · sbuf {badges.sbufLevel}
          </span>
        )}
      </figcaption>
    </figure>
  );
}
