import { expect, test } from "@playwright/test";
import { t } from "../../src/i18n";
import { API_BASE_URL } from "../../src/lib/config";

/**
 * Budget de performance des espaces partenaires (POLISH_CONTRACT §11, même méthode que le comptoir) :
 * « 3G rapide » (1,6 Mb/s, RTT 150 ms, processeur ×4). Le contrat fixe le LCP < 2,5 s pour le
 * comptoir et le lien de paiement ; ici, en mode démonstration, les données arrivent après le
 * démarrage du service worker MSW (absent en production) : le LCP est donc RELEVÉ (annotation,
 * PERFORMANCE.md) et le budget de 2,5 s s'applique au premier affichage du titre, rendu serveur.
 * CLS < 0,1, polices ≤ 110 Ko, aucune ressource hors origine sauf l'API de l'instance (ni CDN, ni traceur).
 */
test("portefeuille assureur : LCP, CLS, polices, aucune ressource tierce", async ({ page, baseURL }) => {
  test.setTimeout(120_000);
  const cdp = await page.context().newCDPSession(page);
  await cdp.send("Network.enable");
  await cdp.send("Network.emulateNetworkConditions", { offline: false, latency: 150, downloadThroughput: (1.6 * 1024 * 1024) / 8, uploadThroughput: (750 * 1024) / 8 });
  await cdp.send("Emulation.setCPUThrottlingRate", { rate: 4 });
  await page.addInitScript(() => window.localStorage.setItem("mulemacare-one.partenaires.demo-role", "assureur"));
  await page.goto("/assureur", { waitUntil: "load" });
  await expect(page.getByRole("heading", { level: 1, name: t("insurer.title") })).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("portfolio")).toBeVisible({ timeout: 30_000 });
  const m = await page.evaluate(async () => {
    await document.fonts.ready;
    let lcp = 0;
    const fcp = performance.getEntriesByName("first-contentful-paint")[0]?.startTime ?? Number.POSITIVE_INFINITY;
    let cls = 0;
    new PerformanceObserver((l) => l.getEntries().forEach((e) => (lcp = e.startTime))).observe({ type: "largest-contentful-paint", buffered: true });
    new PerformanceObserver((l) => (l.getEntries() as (PerformanceEntry & { value: number; hadRecentInput: boolean })[]).forEach((e) => (cls += e.hadRecentInput ? 0 : e.value))).observe({ type: "layout-shift", buffered: true });
    await new Promise((r) => setTimeout(r, 500));
    const resources = performance.getEntriesByType("resource") as PerformanceResourceTiming[];
    return {
      fcp,
      lcp,
      cls,
      fonts: resources.filter((r) => r.name.endsWith(".woff2")).reduce((s, r) => s + r.encodedBodySize, 0),
      foreign: resources.map((r) => new URL(r.name).origin).filter((o) => o !== location.origin),
    };
  });
  test.info().annotations.push({ type: "mesures", description: JSON.stringify(m) });
  expect(m.fcp).toBeLessThan(2_500);
  expect(m.cls).toBeLessThan(0.1);
  expect(m.fonts).toBeLessThanOrEqual(110 * 1024);
  // Seule l'API de l'instance est admise hors de l'origine de la page (aucun CDN, aucun traceur).
  expect(m.foreign.filter((o) => o !== new URL(API_BASE_URL).origin), String(baseURL)).toEqual([]);
});
