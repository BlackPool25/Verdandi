import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// T4 owns this config. Dev serves /sim on port 19104 via CLI flag:
//   npm run dev -- --port 19104
// VITE_BRIDGE_URL overrides the proxy target in Docker (compose sets it to http://api:8000).
const bridge = process.env["VITE_BRIDGE_URL"] ?? "http://localhost:8000";
export default defineConfig({
  plugins: [react()],
  server: {
    port: 19104,
    // Dev-only: same-origin /schema|/stream|/episode proxy to the sim bridge
    // (Manual-QA channel; production wiring lands with T10 stream lifecycle).
    proxy: {
      "/schema": bridge,
      "/stream": bridge,
      "/episode": bridge,
    },
  },
});
