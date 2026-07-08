import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// API requests are proxied to FastAPI in dev so the client can use
// relative URLs and avoid CORS entirely when run through Vite.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://localhost:8000",
      "/health": "http://localhost:8000",
    },
  },
});
