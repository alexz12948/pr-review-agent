import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Assets are served by FastAPI under /static, and the API lives on the same
// origin. During `vite dev`, proxy API calls to the FastAPI server on :8000.
export default defineConfig({
  base: "/static/",
  plugins: [react()],
  build: {
    outDir: "dist",
    emptyOutDir: true,
  },
  server: {
    proxy: {
      "/api": "http://127.0.0.1:8000",
      "/health": "http://127.0.0.1:8000",
    },
  },
});
