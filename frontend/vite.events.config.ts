import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// T9-owned dev/test config: same root as the scaffold, plus a same-origin
// proxy so the events harness can POST /episode and read /stream without
// touching vite.config.ts or the bridge's CORS surface.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 19109,
    strictPort: true,
    proxy: {
      "/episode": "http://127.0.0.1:18009",
      "/stream": "http://127.0.0.1:18009",
      "/health": "http://127.0.0.1:18009",
      "/schema": "http://127.0.0.1:18009",
    },
  },
});
