import { defineConfig, devices } from "@playwright/test";

const port = Number(process.env.CONSOLE_PORT ?? 3416);

/**
 * Parcours de la console contre le serveur de mocks MSW (contrat specs/openapi.yaml).
 * Le serveur est construit en mode mock puis servi en production locale.
 */
export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: [["list"]],
  timeout: 30_000,
  expect: { timeout: 7_000 },
  use: {
    baseURL: `http://127.0.0.1:${port}`,
    locale: "fr-FR",
    timezoneId: "Africa/Abidjan",
    viewport: { width: 1440, height: 900 },
    trace: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } } }],
  webServer: {
    command: `pnpm build:mock && pnpm exec next start --port ${port} --hostname 127.0.0.1`,
    url: `http://127.0.0.1:${port}`,
    reuseExistingServer: !process.env.CI,
    timeout: 240_000,
    stdout: "pipe",
  },
});
