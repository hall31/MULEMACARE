import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    include: ["brand/**/*.test.ts", "security/**/*.test.ts"],
    environment: "node",
  },
});
