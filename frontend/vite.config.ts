import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": path.resolve(__dirname, "./src") },
  },
  server: { port: 5173 },
  build: {
    // Source maps for prod crash triage so Sentry / browser devtools can
    // resolve the minified stack back to original file:line.
    sourcemap: true,
  },
});
