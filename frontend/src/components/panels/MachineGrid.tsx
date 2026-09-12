// T8 32-row machine grid. 32 rows render trivially — virtualization
// skipped (no dependency, no windowing code for 32 <button>s).
import { MACHINE_META } from "./machineMeta";

const BOX: React.CSSProperties = {
  border: "1px solid #888",
  background: "#111",
  color: "#eee",
  padding: 8,
  fontSize: 16,
};

export const GRID_IDS: readonly string[] = [
  ...Object.keys(MACHINE_META),
  "_C7TAIL",
];

export function MachineGrid(props: {
  readonly selectedId: string | null;
  readonly onSelect: (id: string) => void;
}): React.JSX.Element {
  return (
    <section aria-label="machine grid" data-testid="machine-grid" style={BOX}>
      <h2 className="px-h2">Machines</h2>
      <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
        {GRID_IDS.map((id) => (
          <li key={id}>
            <button
              type="button"
              data-testid={`select-${id}`}
              aria-pressed={props.selectedId === id}
              onClick={() => props.onSelect(id)}
            >
              {id}
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
