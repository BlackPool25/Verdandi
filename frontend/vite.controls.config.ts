import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// T7-owned dev/test config: same root as the T4 scaffold, plus a
// same-origin proxy so the controls harness can POST /episode and read
// /stream without touching T4's vite.config.ts or the bridge's CORS surface.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 19104,
    strictPort: true,
    proxy: {
      "/episode": "http://127.0.0.1:18007",
      "/stream": "http://127.0.0.1:18007",
      "/health": "http://127.0.0.1:18007",
      "/schema": "http://127.0.0.1:18007",
    },
  },
});
