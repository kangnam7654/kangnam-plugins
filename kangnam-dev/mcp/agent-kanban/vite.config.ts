import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  root: ".",
  publicDir: "public",
  server: {
    host: "127.0.0.1",
    port: 3001,
    proxy: {
      "/api": "http://127.0.0.1:3100"
    }
  },
  build: {
    outDir: "dist/web",
    emptyOutDir: false
  }
});
