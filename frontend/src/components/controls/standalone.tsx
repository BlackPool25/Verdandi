import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { ControlsBar } from "./ControlsBar";

const rootEl = document.getElementById("root");
if (rootEl === null) {
  throw new Error("missing #root element");
}
createRoot(rootEl).render(
  <StrictMode>
    <main>
      <h1>Sim controls (T7 harness)</h1>
      <ControlsBar />
    </main>
  </StrictMode>,
);
