import { useEffect, useRef } from "react";
import type { EpisodeAnomalySummary } from "./anomalyAnalysis";

interface AnomalyHeatmapProps {
  readonly summary: EpisodeAnomalySummary;
  readonly cursor: number;
  readonly selectedId: string | null;
  readonly onSeek: (step: number) => void;
  readonly onSelectMachine: (id: string) => void;
}

// Colors according to Okabe-Ito / Verdandi palette
const STATE_COLORS: Record<string, string> = {
  RUN: "#009e73", // Green
  STARVED: "#56b4e9", // Sky Blue
  BLOCKED: "#e69f00", // Yellow-orange
  DOWN: "#d55e00", // Red-orange
  IDLE: "#e2d2ac", // Paper-300
};

export function AnomalyHeatmap({
  summary,
  cursor,
  selectedId,
  onSeek,
  onSelectMachine,
}: AnomalyHeatmapProps): React.JSX.Element {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  const { stateMatrix, machineList, totalSteps } = summary;
  const numMachines = machineList.length; // 26
  const numSteps = Math.max(1, totalSteps);

  // Redraw canvas whenever stateMatrix, cursor, or selectedId changes
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const width = canvas.width;
    const height = canvas.height;

    // Clear canvas
    ctx.fillStyle = "#fbf4e2"; // Paper-100
    ctx.fillRect(0, 0, width, height);

    if (numSteps === 0 || numMachines === 0) return;

    const cellW = width / numSteps;
    const cellH = height / numMachines;

    // Draw cells
    for (let m = 0; m < numMachines; m++) {
      const row = stateMatrix[m];
      if (!row) continue;
      const machId = machineList[m];
      const isSelected = machId === selectedId;

      for (let s = 0; s < numSteps; s++) {
        const state = row[s] ?? "IDLE";
        const color = STATE_COLORS[state] ?? "#e2d2ac";
        ctx.fillStyle = color;
        ctx.fillRect(Math.floor(s * cellW), Math.floor(m * cellH), Math.ceil(cellW), Math.ceil(cellH));
      }

      // If selected machine, draw subtle horizontal highlight outline
      if (isSelected) {
        ctx.strokeStyle = "#141b26";
        ctx.lineWidth = 1;
        ctx.strokeRect(0, Math.floor(m * cellH), width, Math.ceil(cellH));
      }
    }

    // Draw grid horizontal dividers between lines A, B, C, ASM, PKG
    const lineBoundaries = [6, 13, 18, 23]; // After A9, B9, C7, RWK0
    ctx.strokeStyle = "#1b2430";
    ctx.lineWidth = 1.5;
    for (const b of lineBoundaries) {
      const y = Math.floor(b * cellH);
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(width, y);
      ctx.stroke();
    }

    // Draw vertical playhead line at current cursor
    if (cursor >= 0 && cursor < numSteps) {
      const x = Math.floor(cursor * cellW);
      ctx.strokeStyle = "#141b26";
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, height);
      ctx.stroke();

      // Top triangle cursor pip
      ctx.fillStyle = "#141b26";
      ctx.beginPath();
      ctx.moveTo(x - 4, 0);
      ctx.lineTo(x + 4, 0);
      ctx.lineTo(x, 6);
      ctx.fill();
    }
  }, [stateMatrix, machineList, numSteps, numMachines, cursor, selectedId]);

  const handleCanvasClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const clickX = e.clientX - rect.left;
    const clickY = e.clientY - rect.top;

    const stepFrac = clickX / rect.width;
    const step = Math.min(numSteps - 1, Math.max(0, Math.floor(stepFrac * numSteps)));

    const machFrac = clickY / rect.height;
    const machIdx = Math.min(numMachines - 1, Math.max(0, Math.floor(machFrac * numMachines)));
    const machId = machineList[machIdx];

    onSeek(step);
    if (machId) {
      onSelectMachine(machId);
    }
  };

  return (
    <div className="vd-heatmap-container" style={{ display: "flex", gap: 8, alignItems: "stretch" }}>
      {/* Station Y-axis labels */}
      <div
        className="vd-heatmap-labels"
        style={{
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          padding: "2px 0",
          fontFamily: "var(--font-display, monospace)",
          fontSize: 9,
          color: "var(--text-muted)",
          width: 52,
          flexShrink: 0,
        }}
      >
        {machineList.map((id) => (
          <div
            key={id}
            onClick={() => onSelectMachine(id)}
            style={{
              cursor: "pointer",
              fontWeight: id === selectedId ? "bold" : "normal",
              color: id === selectedId ? "var(--ink-950)" : "inherit",
              background: id === selectedId ? "var(--paper-300)" : "transparent",
              padding: "0 2px",
            }}
            title={`Select ${id}`}
          >
            {id}
          </div>
        ))}
      </div>

      {/* Heatmap canvas */}
      <div style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column" }}>
        <canvas
          ref={canvasRef}
          width={900}
          height={312}
          onClick={handleCanvasClick}
          style={{
            width: "100%",
            height: 312,
            border: "2px solid var(--ink-900)",
            cursor: "crosshair",
            imageRendering: "pixelated",
            background: "var(--paper-100)",
          }}
          title="Click to seek simulation step and select station"
        />

        {/* X-axis step timeline labels */}
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            fontSize: 10,
            fontFamily: "var(--font-display, monospace)",
            color: "var(--text-muted)",
            marginTop: 4,
          }}
        >
          <span>STEP 0</span>
          <span>STEP 75</span>
          <span>STEP 150</span>
          <span>STEP 225</span>
          <span>STEP 299</span>
        </div>
      </div>
    </div>
  );
}
