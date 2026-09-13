import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

// T12 gate-owned copy of the reduced-motion contract (the T9 anomaly spec
// asserts the same CSS; this copy keeps the gate green even if T9 files move).
const HERE = dirname(fileURLToPath(import.meta.url));

describe("gate: prefers-reduced-motion disables anomaly blink", () => {
  const css = readFileSync(resolve(HERE, "../components/events/events.css"), "utf8");

  it("gt blink uses steps() and reduce-motion pins a static outline", () => {
    expect(css).toContain("steps(");
    expect(css).toContain("@media (prefers-reduced-motion: reduce)");
    const tail = css.slice(css.indexOf("@media (prefers-reduced-motion: reduce)"));
    expect(tail).toContain("animation: none");
  });
});
