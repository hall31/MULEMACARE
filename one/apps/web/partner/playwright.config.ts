import { defineConfig, devices } from "@playwright/test";

const port = Number(process.env.PARTNER_PORT ?? 3420);

/**
 * Espaces assureur et employeur contre les mocks MSW issus du contrat (mode démonstration), build
 * de production servi en local. Marque blanche : organisations fictives choisies par cookie.
 */
export default defineConfig({
  testDir: "./tests/e2e",
  outputDir: "test-results",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: 0,
  workers: process.env.CI ? 2 : undefined,
  reporter: [["list"]],
  timeout: 60_000,
  expect: { timeout: 10_000 },
  use: {
    baseURL: `http://127.0.0.1:${port}`,
    locale: "fr-FR",
    timezoneId: "Africa/Abidjan",
    viewport: { width: 1280, height: 900 },
    trace: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"], viewport: { width: 1280, height: 900 } } }],
  webServer: {
    command: `node_modules/.bin/next build && node_modules/.bin/next start --port ${port} --hostname 127.0.0.1`,
    url: `http://127.0.0.1:${port}`,
    reuseExistingServer: !process.env.CI,
    timeout: 300_000,
    stdout: "pipe",
    env: { NEXT_TELEMETRY_DISABLED: "1", NEXT_PUBLIC_API_MOCKING: "enabled" },
  },
});
