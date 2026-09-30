// `npm run build` writes one self-contained file, public/index.html, served by FastAPI locally and by Vercel.
// `npm run dev` proxies /api to `uvicorn api.index:app` on port 8000.
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { viteSingleFile } from "vite-plugin-singlefile";

export default defineConfig({
  plugins: [react(), viteSingleFile()],
  server: { proxy: { "/api": "http://localhost:8000" } },
  build: { outDir: "../public", emptyOutDir: false },
});
