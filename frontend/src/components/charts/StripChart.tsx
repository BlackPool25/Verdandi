import { useEffect, useRef } from "react";
import type { TwinStore } from "../../store/twinStore";
import { decimateMinMax } from "../../store/ring";
import { paintMinMax } from "./paintStrip";
import { useBadges } from "./useBadges";

export interface StripChartProps {
  readonly store: TwinStore;
  readonly machineId: string;
  readonly title?: string;
  readonly width?: number;
  readonly height?: number;
  readonly min?: number;
  readonly max?: number;
  readonly unit?: string;
  readonly source?: "obs" | "current" | "buffer";
  readonly testidSuffix?: string;
}

export function StripChart({
  store,
  machineId,
  title,
  width = 280,
  height = 68,
  min = 0,
  max = 100,
  unit,
  source = "obs",
  testidSuffix = "",
}: StripChartProps): React.JSX.Element {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const dirtyRef = useRef(true);
  const badges = useBadges(store);

  useEffect(() => {
    dirtyRef.current = true;
  }, [machineId, source, min, max]);

  useEffect(() => {
    return store.subscribeTransient(() => {
      dirtyRef.current = true;
    });
  }, [store]);

  useEffect(() => {
    let raf = 0;
    const frame = (): void => {
      raf = requestAnimationFrame(frame);
      if (!dirtyRef.current) return;
      if (typeof document !== "undefined" && document.hidden) return;
      const canvas = canvasRef.current;
      if (canvas === null) return;
      if (!canvas.isConnected) return;
      const rect = canvas.getBoundingClientRect();
      if (rect.width === 0 || rect.height === 0) return;
      dirtyRef.current = false;
      const ctx = canvas.getContext("2d");
      if (ctx === null) return;

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

      // Whitish canvas surface
      ctx.fillStyle = "#ffffff";
      ctx.fillRect(0, 0, width, height);

      // Subtle canvas grid lines
      ctx.strokeStyle = "#eee9db";
      ctx.lineWidth = 1;
      ctx.beginPath();
      const midY = Math.round(height / 2) + 0.5;
      ctx.moveTo(0, midY);
      ctx.lineTo(width, midY);
      for (const pct of [0.25, 0.5, 0.75]) {
        const gx = Math.round(width * pct) + 0.5;
        ctx.moveTo(gx, 0);
        ctx.lineTo(gx, height);
      }
      ctx.stroke();

      const data =
        source === "current"
          ? store.currentSeries(machineId)
          : source === "buffer"
          ? store.bufferSeries(machineId)
          : store.series(machineId);
      const pairs = decimateMinMax(data, Math.max(1, Math.floor(width)));

      ctx.strokeStyle =
        source === "current" ? "#7c3aed" : source === "buffer" ? "#059669" : "#1b4965";
      ctx.lineWidth = 1.5;
      paintMinMax(ctx, { pairs, min, max, w: width, h: height, totalSteps: 300 });

      // Playhead cursor at active step
      if (badges.cursor >= 0 && badges.cursor < 300) {
        const curX = Math.round((badges.cursor / 299) * width) + 0.5;
        ctx.strokeStyle = "#e5484d";
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(curX, 0);
        ctx.lineTo(curX, height);
        ctx.stroke();
      }

      store.paintDirty();
    };
    raf = requestAnimationFrame(frame);
    return () => {
      cancelAnimationFrame(raf);
    };
  }, [store, machineId, width, height, min, max, source, badges.cursor]);

  const defaultTitle =
    source === "current"
      ? "MOTOR CURRENT, A (CH8)"
      : source === "buffer"
      ? "BUFFER OCCUPANCY"
      : "OBSERVATION TELEMETRY";
  const displayTitle = title ?? defaultTitle;

  const defaultUnit =
    source === "current" ? "Amps (A)" : source === "buffer" ? "parts" : "Units";
  const displayUnit = unit ?? defaultUnit;

  const yMax = Math.round(max);
  const yMid = Math.round((min + max) / 2);
  const yMin = Math.round(min);

  return (
    <figure
      data-testid={`strip-${machineId}${testidSuffix}`}
      aria-label={`${machineId} strip chart`}
      className="strip-chart-card"
    >
      <div className="strip-chart-header">
        <span className="strip-chart-title">{displayTitle}</span>
        <span className="strip-chart-scale-tag">{displayUnit}</span>
      </div>
      <div className="strip-chart-layout">
        <div className="strip-chart-y-axis" aria-label="y axis">
          <span className="strip-chart-y-tick">{yMax}</span>
          <span className="strip-chart-y-tick">{yMid}</span>
          <span className="strip-chart-y-tick">{yMin}</span>
        </div>
        <div className="strip-chart-plot">
          <div className="strip-chart-canvas-wrap">
            <canvas
              ref={canvasRef}
              width={width}
              height={height}
              style={{ width, height, display: "block", maxWidth: "100%" }}
            />
          </div>
          <div className="strip-chart-x-axis" aria-label="x axis">
            <span>0</span>
            <span>150</span>
            <span>300 steps</span>
          </div>
        </div>
      </div>
      <figcaption className="strip-chart-caption">
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
