import { defineConfig, devices } from "@playwright/test";

// Port libre à choisir si 3100 est déjà pris (sinon `reuseExistingServer` testerait un autre serveur).
const PORT = Number(process.env.COUNTER_E2E_PORT ?? 3100);

/**
 * Parcours du comptoir sur un téléphone Android d'entrée de gamme (360 × 780, tactile).
 * L'API est simulée dans le navigateur (e2e/mock-api.ts) ; le serveur Next relaie /api vers un
 * port fermé, donc toute requête non simulée échoue au lieu de partir sur le réseau.
 */
export default defineConfig({
  testDir: "e2e",
  outputDir: "test-results",
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: 0,
  reporter: [["list"]],
  use: {
    ...devices["Desktop Chrome"],
    baseURL: `http://127.0.0.1:${PORT}`,
    viewport: { width: 360, height: 780 },
    deviceScaleFactor: 2,
    isMobile: true,
    hasTouch: true,
    locale: "fr-FR",
    timezoneId: "Africa/Abidjan",
    serviceWorkers: "block",
    trace: "retain-on-failure",
  },
  projects: [{ name: "android-chromium" }],
  webServer: {
    command: `node_modules/.bin/next build && node_modules/.bin/next start -p ${PORT} -H 127.0.0.1`,
    url: `http://127.0.0.1:${PORT}`,
    reuseExistingServer: !process.env.CI,
    timeout: 240_000,
    env: {
      NEXT_TELEMETRY_DISABLED: "1",
      NEXT_PUBLIC_MULEMA_AUTH_MODE: "test",
      MULEMA_API_URL: "http://127.0.0.1:9",
      // Marque blanche (P3) : organisations fictives choisies par le cookie `mc-org` ; sans cookie,
      // thème MulemaCare (les autres parcours sont inchangés).
      MULEMA_BRANDING_FIXTURES: "enabled",
    },
  },
});
