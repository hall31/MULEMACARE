import { expect, test, type Page } from "@playwright/test";
import { PAYMENT_TOKEN } from "../src/test/fixtures";
import { fr, tr } from "./flow";
import { MockApi } from "./mock-api";

/**
 * Budgets de performance (PERFORMANCE.md, contrat de design §11), comme le comptoir
 * (apps/web/counter/e2e/perf.spec.ts) : LCP < 2,5 s, CLS < 0,1, JavaScript initial ≤ 170 Ko et
 * polices ≤ 110 Ko sur un profil « 3G rapide » (1,6 Mb/s, RTT 150 ms, processeur ralenti ×4), par
 * CDP, sur la carte (écran d'ouverture de l'espace) et sur le lien de paiement public.
 */
const LCP_BUDGET_MS = 2_500;
const CLS_BUDGET = 0.1;
const JS_BUDGET_BYTES = 170 * 1024;
/** Tout le JavaScript reçu dans les 1,2 premières secondes, préchargements et encodeur du QR compris. */
const JS_ALL_BUDGET_BYTES = 200 * 1024;
const FONT_BUDGET_BYTES = 110 * 1024;

async function measure(page: Page, path: string, heading: string) {
  const cdp = await page.context().newCDPSession(page);
  await cdp.send("Network.enable");
  await cdp.send("Network.setCacheDisabled", { cacheDisabled: true });
  await cdp.send("Network.emulateNetworkConditions", {
    offline: false,
    latency: 150,
    downloadThroughput: (1.6 * 1024 * 1024) / 8,
    uploadThroughput: (750 * 1024) / 8,
  });
  await cdp.send("Emulation.setCPUThrottlingRate", { rate: 4 });

  await page.goto(path, { waitUntil: "load" });
  await expect(page.getByRole("heading", { level: 1, name: heading })).toBeVisible();

  const metrics = await page.evaluate(async () => {
    await document.fonts.ready;
    await new Promise((resolve) => setTimeout(resolve, 1_000));
    let lcp = 0;
    let lcpElement = "";
    let cls = 0;
    new PerformanceObserver((list) => {
      for (const entry of list.getEntries() as (PerformanceEntry & { element?: Element | null })[]) {
        lcp = entry.startTime;
        lcpElement = entry.element ? `${entry.element.tagName.toLowerCase()}.${entry.element.className}` : "";
      }
    }).observe({ type: "largest-contentful-paint", buffered: true });
    new PerformanceObserver((list) => {
      for (const entry of list.getEntries() as (PerformanceEntry & { value: number; hadRecentInput: boolean })[]) if (!entry.hadRecentInput) cls += entry.value;
    }).observe({ type: "layout-shift", buffered: true });
    await new Promise((resolve) => setTimeout(resolve, 200));
    const resources = performance.getEntriesByType("resource") as PerformanceResourceTiming[];
    const sum = (filter: (r: PerformanceResourceTiming) => boolean) => resources.filter(filter).reduce((total, r) => total + r.encodedBodySize, 0);
    // JavaScript initial = scripts référencés par le HTML servi (ce que le navigateur doit
    // télécharger pour afficher l'écran). Les morceaux chargés ensuite (encodeur du QR après les
    // données, préchargement des onglets par next/link) sont comptés à part dans `jsAllBytes`.
    const html = await (await fetch(location.pathname, { cache: "no-store" })).text();
    const initial = new Set([...html.matchAll(/\/_next\/static\/[^"'\s]+?\.js/g)].map((m) => new URL(m[0], location.origin).href));
    const isJs = (r: PerformanceResourceTiming) => r.initiatorType === "script" || r.name.endsWith(".js");
    return {
      lcp: Math.round(lcp),
      lcpElement,
      cls: Number(cls.toFixed(3)),
      jsBytes: sum((r) => isJs(r) && initial.has(r.name)),
      jsAllBytes: sum(isJs),
      fontBytes: sum((r) => r.name.endsWith(".woff2")),
      fonts: resources.filter((r) => r.name.endsWith(".woff2")).length,
      externalOrigins: [...new Set(resources.map((r) => new URL(r.name).origin).filter((origin) => origin !== location.origin))],
    };
  });
  await cdp.send("Emulation.setCPUThrottlingRate", { rate: 1 });
  return metrics;
}

const PAGES = [
  { name: "ma carte", path: "/", heading: fr["card.title"] },
  { name: "lien de paiement", path: `/payer/${PAYMENT_TOKEN}`, heading: tr("pay.title", { period: "d’octobre 2026", initials: "A. K." }) },
];

test.describe("premier affichage sur 3G rapide, processeur ×4", () => {
  for (const target of PAGES) {
    test(`${target.name} : LCP, CLS, poids JS et polices`, async ({ page }) => {
      await new MockApi().install(page);
      const metrics = await measure(page, target.path, target.heading);
      test.info().annotations.push({ type: `mesure 3G rapide — ${target.name}`, description: JSON.stringify(metrics) });
      console.log(`[perf] ${target.name}`, metrics);
      expect(metrics.externalOrigins, "aucune ressource hors de l'origine (polices comprises)").toEqual([]);
      expect.soft(metrics.lcp, `LCP ${metrics.lcp} ms (${metrics.lcpElement})`).toBeLessThan(LCP_BUDGET_MS);
      expect.soft(metrics.cls, "CLS").toBeLessThan(CLS_BUDGET);
      expect.soft(metrics.jsBytes, "JavaScript initial compressé").toBeLessThanOrEqual(JS_BUDGET_BYTES);
      expect.soft(metrics.jsAllBytes, "JavaScript total des premières secondes").toBeLessThanOrEqual(JS_ALL_BUDGET_BYTES);
      expect.soft(metrics.fontBytes, "polices").toBeLessThanOrEqual(FONT_BUDGET_BYTES);
    });
  }
});

test("ma carte, API lente (1,5 s) : la place est réservée, CLS < 0,1", async ({ page }) => {
  const api = new MockApi();
  for (const path of ["/v1/me/card", "/v1/me/claims", "/v1/me/contributions"]) api.delays.set(path, 1_500);
  await api.install(page);
  await page.goto("/", { waitUntil: "load" });
  await expect(page.getByTestId("member-card")).toBeVisible({ timeout: 10_000 });
  await expect(page.getByTestId("home-contribution")).toBeVisible({ timeout: 10_000 });
  const cls = await page.evaluate(
    () =>
      new Promise<number>((resolve) => {
        let total = 0;
        new PerformanceObserver((list) => {
          for (const entry of list.getEntries() as (PerformanceEntry & { value: number; hadRecentInput: boolean })[]) if (!entry.hadRecentInput) total += entry.value;
        }).observe({ type: "layout-shift", buffered: true });
        setTimeout(() => resolve(Number(total.toFixed(3))), 300);
      }),
  );
  test.info().annotations.push({ type: "CLS, API lente", description: String(cls) });
  console.log("[perf] ma carte, API lente : CLS", cls);
  expect(cls).toBeLessThan(CLS_BUDGET);
});
