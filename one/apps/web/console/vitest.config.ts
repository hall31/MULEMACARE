import path from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

const here = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  resolve: { alias: { "@": path.resolve(here, "src"), "@shared": path.resolve(here, "../shared") } },
  // Vite 8 transforme via Oxc (l'option `esbuild` est dépréciée et rejetée au typage).
  oxc: { jsx: { runtime: "automatic" } },
  test: {
    include: ["tests/unit/**/*.test.{ts,tsx}"],
    environment: "node",
    setupFiles: ["tests/unit/setup.ts"],
    restoreMocks: true,
  },
});
