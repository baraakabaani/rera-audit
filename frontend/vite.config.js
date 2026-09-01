import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The backend runs on :8000. All calls go through /api and are proxied in dev.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: process.env.VITE_API_TARGET || "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
