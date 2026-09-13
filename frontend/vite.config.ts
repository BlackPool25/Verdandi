import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// T4 owns this config. Dev serves /sim on port 19104 via CLI flag:
//   npm run dev -- --port 19104
export default defineConfig({
  plugins: [react()],
  server: {
    port: 19104,
    // Dev-only: same-origin /schema|/stream|/episode proxy to the sim bridge
    // (Manual-QA channel; production wiring lands with T10 stream lifecycle).
    proxy: {
      "/schema": "http://localhost:8000",
      "/stream": "http://localhost:8000",
      "/episode": "http://localhost:8000",
    },
  },
});
