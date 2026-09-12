import { useState } from "react";
import { EXTRA_HINTS, FAULT_CLASS_OPTIONS, MACHINES, type FaultDraft } from "./types";

interface FaultFormProps {
  faults: FaultDraft[];
  onAdd: (f: FaultDraft) => void;
  onRemove: (id: string) => void;
}

let idSeq = 0;

function parseExtra(text: string): { ok: true; value: Record<string, number> } | { ok: false; error: string } {
  const trimmed = text.trim();
  if (trimmed === "") return { ok: true, value: {} };
  try {
    const v: unknown = JSON.parse(trimmed);
    if (typeof v !== "object" || v === null || Array.isArray(v)) {
      return { ok: false, error: "extra must be a JSON object" };
    }
    return { ok: true, value: v as Record<string, number> };
  } catch {
    return { ok: false, error: "extra must be a JSON object" };
  }
}

export function FaultForm({ faults, onAdd, onRemove }: FaultFormProps): React.JSX.Element {
  const [faultClass, setFaultClass] = useState<string>("drift");
  const [origin, setOrigin] = useState<string>("B5");
  const [t0, setT0] = useState<string>("150");
  const [dur, setDur] = useState<string>("12");
  const [extra, setExtra] = useState<string>("{}");
  const [extraError, setExtraError] = useState<string>("");

  const hint = EXTRA_HINTS[faultClass] ?? "";

  function handleAdd(): void {
    const parsed = parseExtra(extra);
    if (!parsed.ok) {
      setExtraError(parsed.error);
      return;
    }
    setExtraError("");
    idSeq += 1;
    onAdd({
      id: `F-UI${idSeq}`,
      faultClass,
      origin,
      t0: Number(t0),
      dur: Number(dur),
      extra: parsed.value,
    });
  }

  return (
    <section aria-label="fault form">
      <label>
        class (STUCK label→breakdown)
        <select data-testid="fault-class" value={faultClass} onChange={(e) => setFaultClass(e.target.value)}>
          {FAULT_CLASS_OPTIONS.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
      </label>
      <label>
        origin
        <select data-testid="fault-origin" value={origin} onChange={(e) => setOrigin(e.target.value)}>
          {MACHINES.map((m) => (
            <option key={m} value={m}>
              {m}
            </option>
          ))}
        </select>
      </label>
      <label>
        t0 (≥120)
        <input data-testid="fault-t0" inputMode="numeric" value={t0} onChange={(e) => setT0(e.target.value)} />
      </label>
      <label>
        dur (1–25, bridge-strict 8–25)
        <input data-testid="fault-dur" inputMode="numeric" value={dur} onChange={(e) => setDur(e.target.value)} />
      </label>
      <label>
        extra JSON
        <input data-testid="fault-extra" value={extra} onChange={(e) => setExtra(e.target.value)} />
      </label>
      <p data-testid="extra-hint">{hint}</p>
      {extraError !== "" && <p data-testid="extra-error">{extraError}</p>}
      <button type="button" data-testid="fault-add" onClick={handleAdd}>
        Add fault
      </button>
      <ul data-testid="fault-list">
        {faults.map((f) => (
          <li key={f.id}>
            {f.id} {f.faultClass}@{f.origin} t0={f.t0} dur={f.dur} extra={JSON.stringify(f.extra)}{" "}
            <button type="button" data-testid={`fault-remove-${f.id}`} onClick={() => onRemove(f.id)}>
              Remove
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
