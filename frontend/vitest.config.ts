import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// T12 owns this config: bare `vitest run` / `npm test` collects ONLY unit
// specs. Playwright e2e specs (e2e/*.spec.ts import @playwright/test) fail
// collection under vitest — pre-existing noise since T4. Harness
// `standalone` modules and per-harness vite configs are likewise excluded.
export default defineConfig({
  plugins: [react()],
  test: {
    include: ["src/**/*.spec.ts", "src/**/*.spec.tsx"],
    exclude: [
      "node_modules",
      "dist",
      "e2e/**",
      "**/*.standalone.*",
      "**/standalone.*",
      "vite.*.config.ts",
      "playwright.config.ts",
    ],
  },
});
