import { expect, test, type Page } from "@playwright/test";
import { GOOD_CODE, MockApi } from "./mock-api";
import { fr, selectActs, xof } from "./flow";

/**
 * Budgets de performance du comptoir (PERFORMANCE.md, contrat de design §11).
 * 1. Parcours chronométré « carte scannée → accord affiché » sur les mocks : chaque interaction
 *    < 1 s jusqu'au titre de l'écran suivant, parcours complet < 10 s (PRD objectif 1).
 * 2. LCP < 2,5 s, CLS < 0,1, JavaScript initial ≤ 170 Ko et polices ≤ 110 Ko sur un profil
 *    « 3G rapide » (1,6 Mb/s, RTT 150 ms, processeur ralenti ×4), par CDP.
 */
const INTERACTION_BUDGET_MS = 1_000;
const JOURNEY_BUDGET_MS = 10_000;
const LCP_BUDGET_MS = 2_500;
const CLS_BUDGET = 0.1;
const JS_BUDGET_BYTES = 170 * 1024;
const FONT_BUDGET_BYTES = 110 * 1024;

/** Charge utile du QR : fictive (le mock accepte toute charge utile signée par la carte). */
const QR_PAYLOAD = "MC1.carte-fictive.signature-de-test";

/**
 * Caméra et détecteur simulés : un flux issu d'un canevas (aucun appareil réel) et un
 * BarcodeDetector qui « lit » le QR fictif. Le code du comptoir reste celui de production.
 */
async function fakeCamera(page: Page): Promise<void> {
  await page.addInitScript((payload: string) => {
    const canvas = document.createElement("canvas");
    canvas.width = 320;
    canvas.height = 240;
    const ctx = canvas.getContext("2d");
    const paint = () => {
      ctx?.fillRect(0, 0, 1 + (Date.now() % 50), 1);
      requestAnimationFrame(paint);
    };
    paint();
    Object.defineProperty(navigator, "mediaDevices", {
      configurable: true,
      value: { getUserMedia: async () => canvas.captureStream(15) },
    });
    class FakeBarcodeDetector {
      async detect(): Promise<{ rawValue: string }[]> {
        return [{ rawValue: payload }];
      }
    }
    Object.defineProperty(window, "BarcodeDetector", { configurable: true, value: FakeBarcodeDetector });
  }, QR_PAYLOAD);
}

async function timed(label: string, steps: Record<string, number>, action: () => Promise<void>): Promise<void> {
  const start = Date.now();
  await action();
  steps[label] = Date.now() - start;
}

test.describe("budgets de performance", () => {
  test("parcours chronométré : carte scannée → accord affiché", async ({ page }) => {
    const api = new MockApi();
    await fakeCamera(page);
    await api.install(page);
    await page.goto("/");
    await expect(page.getByRole("heading", { level: 1, name: fr["card.title"] })).toBeVisible();
    await expect.poll(() => api.requests.some((r) => r.path === "/v1/counter/offline-policy")).toBe(true);

    const steps: Record<string, number> = {};
    const journeyStart = Date.now();
    // Le scan inclut l'ouverture de la caméra et la lecture du QR (une image toutes les 300 ms).
    await timed("carte → identité (scan)", steps, async () => {
      await page.getByRole("button", { name: fr["card.scan"] }).click();
      await expect(page.getByRole("heading", { level: 1, name: fr["identity.title"] })).toBeVisible();
    });
    expect(api.requests.find((r) => r.path === "/v1/counter/identifications")?.body).toEqual({ qr_payload: QR_PAYLOAD });

    await timed("identité → code", steps, async () => {
      await page.getByRole("button", { name: fr["identity.yes"] }).click();
      await expect(page.getByRole("heading", { level: 1, name: fr["code.title"] })).toBeVisible();
    });

    await page.getByLabel(fr["code.label"]).fill(GOOD_CODE);
    await timed("code → actes", steps, async () => {
      await page.getByRole("button", { name: fr["code.validate"] }).click();
      await expect(page.getByRole("heading", { level: 1, name: fr["acts.title"] })).toBeVisible();
    });

    await selectActs(page, ["CS-GEN", "NFS", "ECG"]);
    await timed("actes → décision", steps, async () => {
      await page.getByRole("button", { name: fr["acts.submit"] }).click();
      await expect(page.getByRole("heading", { level: 1, name: fr["decision.title.auto"] })).toBeVisible();
      await expect(page.getByTestId("collect")).toContainText(xof(9_600));
    });
    const journey = Date.now() - journeyStart;

    const report = { ...steps, "parcours complet": journey };
    test.info().annotations.push({ type: "mesure (ms)", description: JSON.stringify(report) });
    console.log("[perf] parcours comptoir (ms)", report);
    for (const [label, ms] of Object.entries(steps)) expect.soft(ms, `${label} : ${ms} ms`).toBeLessThan(INTERACTION_BUDGET_MS);
    expect(journey, `parcours complet : ${journey} ms`).toBeLessThan(JOURNEY_BUDGET_MS);
  });

  test("premier affichage sur 3G rapide : LCP, CLS, poids JS et polices", async ({ page }) => {
    const api = new MockApi();
    await api.install(page);
    const cdp = await page.context().newCDPSession(page);
    await cdp.send("Network.enable");
    await cdp.send("Network.setCacheDisabled", { cacheDisabled: true });
    // Profil Lighthouse « slow 4G / 3G rapide » : 1,6 Mb/s descendant, 750 kb/s montant, RTT 150 ms.
    await cdp.send("Network.emulateNetworkConditions", {
      offline: false,
      latency: 150,
      downloadThroughput: (1.6 * 1024 * 1024) / 8,
      uploadThroughput: (750 * 1024) / 8,
    });
    await cdp.send("Emulation.setCPUThrottlingRate", { rate: 4 });

    await page.goto("/", { waitUntil: "load" });
    await expect(page.getByRole("heading", { level: 1, name: fr["card.title"] })).toBeVisible();

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
      return {
        lcp: Math.round(lcp),
        lcpElement,
        cls: Number(cls.toFixed(3)),
        jsBytes: sum((r) => r.initiatorType === "script" || r.name.endsWith(".js")),
        fontBytes: sum((r) => r.name.endsWith(".woff2")),
        fonts: resources.filter((r) => r.name.endsWith(".woff2")).length,
        externalOrigins: [...new Set(resources.map((r) => new URL(r.name).origin).filter((origin) => origin !== location.origin))],
      };
    });
    await cdp.send("Emulation.setCPUThrottlingRate", { rate: 1 });

    test.info().annotations.push({ type: "mesure 3G rapide", description: JSON.stringify(metrics) });
    console.log("[perf] 3G rapide, processeur ×4", metrics);
    expect(metrics.externalOrigins, "aucune ressource hors de l'origine (polices comprises)").toEqual([]);
    expect.soft(metrics.lcp, `LCP ${metrics.lcp} ms (${metrics.lcpElement})`).toBeLessThan(LCP_BUDGET_MS);
    expect.soft(metrics.cls, "CLS").toBeLessThan(CLS_BUDGET);
    expect.soft(metrics.jsBytes, "JavaScript initial compressé").toBeLessThanOrEqual(JS_BUDGET_BYTES);
    expect.soft(metrics.fontBytes, "polices").toBeLessThanOrEqual(FONT_BUDGET_BYTES);
  });
});
