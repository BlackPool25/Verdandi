import type { EpisodeCreated, FaultDraft, TickRow } from "./types";

export function bridgeBase(): string {
  const q = new URLSearchParams(window.location.search).get("bridge");
  if (q !== null && q !== "") return q.replace(/\/$/, "");
  return "";
}

export class EpisodeError extends Error {
  status: number;
  detail: string;
  constructor(status: number, detail: string) {
    super(`POST /episode → ${status}: ${detail}`);
    this.name = "EpisodeError";
    this.status = status;
    this.detail = detail;
  }
}

interface WireFault {
  id: string;
  class: string;
  origin: string;
  t0: number;
  dur: number;
  extra: Record<string, number>;
}

export async function postEpisode(
  base: string,
  seed: number,
  faults: readonly FaultDraft[],
  enableNaturalBreakdown: boolean,
): Promise<EpisodeCreated> {
  const wire: WireFault[] = faults.map((f) => ({
    id: f.id,
    class: f.faultClass,
    origin: f.origin,
    t0: f.t0,
    dur: f.dur,
    extra: f.extra,
  }));
  const res = await fetch(`${base}/episode`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ seed, faults: wire, enable_natural_breakdown: enableNaturalBreakdown }),
  });
  const body: unknown = await res.json().catch(() => null);
  if (!res.ok) {
    const detail =
      typeof body === "object" && body !== null && "detail" in body && typeof body.detail === "string"
        ? body.detail
        : `HTTP ${res.status}`;
    throw new EpisodeError(res.status, detail);
  }
  return body as EpisodeCreated;
}

export function openTickStream(base: string, episodeId: string, onTick: (row: TickRow) => void): () => void {
  const src = new EventSource(`${base}/stream?episode_id=${encodeURIComponent(episodeId)}`);
  const onTickEvent = (ev: MessageEvent<string>): void => {
    try {
      const data: unknown = JSON.parse(ev.data);
      if (typeof data === "object" && data !== null && "step" in data && typeof data.step === "number") {
        onTick(data as TickRow);
      }
    } catch {
      /* ignore malformed frames; cursor stays put */
    }
  };
  src.addEventListener("tick", onTickEvent as EventListener);
  return () => src.close();
}
