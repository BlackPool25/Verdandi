import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// T9-owned dev/test config: same root as the scaffold, plus a same-origin
// proxy so the events harness can POST /episode and read /stream without
// touching vite.config.ts or the bridge's CORS surface.
const bridge = process.env["VITE_BRIDGE_URL"] ?? "http://127.0.0.1:18009";
export default defineConfig({
  plugins: [react()],
  server: {
    port: 19109,
    strictPort: true,
    proxy: {
      "/episode": bridge,
      "/stream": bridge,
      "/health": bridge,
      "/schema": bridge,
    },
  },
});
