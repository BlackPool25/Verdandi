import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// T7-owned dev/test config: same root as the T4 scaffold, plus a
// same-origin proxy so the controls harness can POST /episode and read
// /stream without touching T4's vite.config.ts or the bridge's CORS surface.
const bridge = process.env["VITE_BRIDGE_URL"] ?? "http://127.0.0.1:18007";
export default defineConfig({
  plugins: [react()],
  server: {
    port: 19104,
    strictPort: true,
    proxy: {
      "/episode": bridge,
      "/stream": bridge,
      "/health": bridge,
      "/schema": bridge,
    },
  },
});
