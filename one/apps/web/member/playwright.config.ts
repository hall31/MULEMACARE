import { defineConfig, devices } from "@playwright/test";

// Port libre à choisir si 3200 est déjà pris (sinon `reuseExistingServer` testerait un autre serveur).
const PORT = Number(process.env.MEMBER_E2E_PORT ?? 3200);

/**
 * Parcours de l'espace adhérent sur un téléphone de 375 × 812 (tactile). L'API est simulée dans
 * le navigateur (e2e/mock-api.ts, typé par le contrat) ; le serveur Next relaie /api vers un port
 * fermé, donc toute requête non simulée échoue au lieu de partir sur le réseau.
 */
export default defineConfig({
  testDir: "e2e",
  // Captures (screenshots/) : seulement sur demande, `make screenshots`.
  testIgnore: process.env.MEMBER_SCREENSHOTS ? [] : ["**/screenshots.spec.ts"],
  outputDir: "test-results",
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: 0,
  workers: process.env.CI ? undefined : 2,
  timeout: 60_000,
  expect: { timeout: 10_000 },
  reporter: [["list"]],
  use: {
    ...devices["Desktop Chrome"],
    baseURL: `http://127.0.0.1:${PORT}`,
    viewport: { width: 375, height: 812 },
    deviceScaleFactor: 2,
    isMobile: true,
    hasTouch: true,
    locale: "fr-FR",
    timezoneId: "Africa/Abidjan",
    serviceWorkers: "block",
    trace: "retain-on-failure",
  },
  projects: [{ name: "mobile-chromium" }],
  webServer: {
    command: `node_modules/.bin/next build && node_modules/.bin/next start -p ${PORT} -H 127.0.0.1`,
    url: `http://127.0.0.1:${PORT}`,
    reuseExistingServer: !process.env.CI,
    timeout: 300_000,
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
