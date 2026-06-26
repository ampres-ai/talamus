import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  base: "./",
  server: { proxy: { "/api": "http://127.0.0.1:8760" } },
  build: {
    outDir: "../src/talamus/webapi/static",
    emptyOutDir: true,
    assetsDir: "assets",
  },
});
