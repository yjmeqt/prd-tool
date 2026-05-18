import { defineConfig, type Plugin } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { fileURLToPath } from "node:url";
import path from "node:path";

const here = path.dirname(fileURLToPath(import.meta.url));
const PYTHON_STATIC = path.resolve(here, "../src/prd_tool/dashboard/static");

// In static-export mode (VITE_STATIC_BASE set) the build is for GitHub Pages /
// other static hosts, so we emit to ./dist instead of overwriting the wheel's
// bundled assets. VITE_BASE lets a deployment serve under a subpath like
// https://<org>.github.io/<repo>/.
const STATIC_MODE = !!process.env.VITE_STATIC_BASE;
const BASE = process.env.VITE_BASE ?? "/";
const OUT_DIR = STATIC_MODE ? path.resolve(here, "dist") : PYTHON_STATIC;

// GitHub Pages serves a static directory: no SPA fallback, and Jekyll strips
// files/directories starting with `_`. We mirror index.html → 404.html so deep
// links into the React Router routes still boot the app, and add .nojekyll so
// Vite's chunk filenames are never filtered.
function ghPagesStaticHostPlugin(): Plugin {
  return {
    name: "prd-tool-gh-pages",
    apply: "build",
    enforce: "post",
    generateBundle(_options, bundle) {
      const index = bundle["index.html"];
      if (index && index.type === "asset") {
        this.emitFile({
          type: "asset",
          fileName: "404.html",
          source: index.source,
        });
      }
      this.emitFile({ type: "asset", fileName: ".nojekyll", source: "" });
    },
  };
}

export default defineConfig({
  base: BASE,
  plugins: [react(), tailwindcss(), ...(STATIC_MODE ? [ghPagesStaticHostPlugin()] : [])],
  resolve: {
    alias: {
      "@": path.resolve(here, "src"),
    },
  },
  server: {
    port: 5173,
    proxy: {
      "/api": "http://127.0.0.1:8765",
    },
  },
  build: {
    outDir: OUT_DIR,
    emptyOutDir: true,
    assetsDir: "assets",
  },
});
