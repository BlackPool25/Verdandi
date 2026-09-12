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
      if (!dirtyRef.current) return;
      dirtyRef.current = false;
      const canvas = canvasRef.current;
      if (canvas === null) return;
      const ctx = canvas.getContext("2d");
      if (ctx === null) return;
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
      <canvas ref={canvasRef} width={width} height={height} />
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
