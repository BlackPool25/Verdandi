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
  const [origin, setOrigin] = useState<string>("B2");
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
    <section aria-label="fault form" className="ctrl-fault-section">
      <div className="ctrl-fault-grid">
        <label className="ctrl-field">
          <span className="ctrl-field-title">CLASS <span className="ctrl-field-sub">(STUCK→breakdown)</span></span>
          <select data-testid="fault-class" value={faultClass} onChange={(e) => setFaultClass(e.target.value)}>
            {FAULT_CLASS_OPTIONS.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </label>
        <label className="ctrl-field">
          <span className="ctrl-field-title">ORIGIN</span>
          <select data-testid="fault-origin" value={origin} onChange={(e) => setOrigin(e.target.value)}>
            {MACHINES.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
        </label>
        <label className="ctrl-field">
          <span className="ctrl-field-title">T0 <span className="ctrl-field-sub">(≥120)</span></span>
          <input data-testid="fault-t0" inputMode="numeric" value={t0} onChange={(e) => setT0(e.target.value)} />
        </label>
        <label className="ctrl-field">
          <span className="ctrl-field-title">DUR <span className="ctrl-field-sub">(8–25)</span></span>
          <input data-testid="fault-dur" inputMode="numeric" value={dur} onChange={(e) => setDur(e.target.value)} />
        </label>
        <label className="ctrl-field ctrl-field-wide">
          <span className="ctrl-field-title">EXTRA JSON</span>
          <input data-testid="fault-extra" value={extra} onChange={(e) => setExtra(e.target.value)} />
        </label>
      </div>

      <div className="ctrl-fault-action-row">
        <button type="button" className="ctrl-btn-primary" data-testid="fault-add" onClick={handleAdd}>
          + Add fault
        </button>
        {hint && <p className="ctrl-field-hint" data-testid="extra-hint">{hint}</p>}
        {extraError !== "" && <p className="ctrl-error-banner" data-testid="extra-error">{extraError}</p>}
      </div>

      <ul className="ctrl-fault-list" data-testid="fault-list">
        {faults.map((f) => (
          <li key={f.id} className="ctrl-fault-item">
            <span className="ctrl-fault-id">{f.id}</span>
            <span className="ctrl-fault-spec">{f.faultClass}@{f.origin} t0={f.t0} dur={f.dur} extra={JSON.stringify(f.extra)}</span>
            <button type="button" className="ctrl-btn-remove" data-testid={`fault-remove-${f.id}`} onClick={() => onRemove(f.id)}>
              Remove
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
