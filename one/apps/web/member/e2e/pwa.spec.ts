import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { card } from "../src/test/fixtures";
import { fr, h1, openCard, tr } from "./flow";
import { MockApi } from "./mock-api";

test.describe("PWA installable, dernière carte lisible hors ligne", () => {
  test.use({ serviceWorkers: "allow" });

  test("manifeste installable", async ({ request }) => {
    const response = await request.get("/manifest.webmanifest");
    expect(response.ok()).toBe(true);
    const manifest = (await response.json()) as Record<string, unknown> & { icons: { sizes: string; purpose?: string; src: string }[] };
    expect(manifest).toMatchObject({ name: fr["app.fullName"], short_name: fr["app.shortName"], start_url: "/", display: "standalone", lang: "fr" });
    expect(manifest.theme_color).toMatch(/^#[0-9a-f]{6}$/i);
    expect(manifest.icons.map((i) => `${i.sizes}:${i.purpose ?? "any"}`)).toEqual(expect.arrayContaining(["192x192:any", "512x512:any", "512x512:maskable"]));
    for (const icon of manifest.icons) expect((await request.get(icon.src)).headers()["content-type"]).toBe("image/png");
  });

  test("réseau coupé au redémarrage : dernière carte enregistrée, QR clairement expiré, rien de l'API en cache", async ({ page, context }) => {
    const api = new MockApi();
    await openCard(page, api);
    await page.evaluate(async () => {
      await navigator.serviceWorker.ready;
    });
    // Deuxième chargement contrôlé par le service worker : il garde la coquille.
    await page.reload();
    await expect.poll(() => page.evaluate(() => Boolean(navigator.serviceWorker.controller))).toBe(true);
    await h1(page, fr["card.title"]);
    await expect(page.getByTestId("qr")).toHaveAttribute("data-ready", "true");

    api.networkDown = true;
    await context.setOffline(true);
    await page.reload();
    await h1(page, fr["card.title"]);
    await expect(page.getByTestId("offline-banner")).toBeVisible();
    const offline = page.getByTestId("card-offline");
    await expect(offline).toBeVisible();
    await expect(offline).toContainText(tr("error.codeLabel", { code: "E-NET-01" }));
    await expect(offline).toContainText(tr("card.offline.number", { number: card.member_number }));
    await expect(page.getByTestId("member-card")).toHaveAttribute("data-phase", "expire");
    await expect(page.getByTestId("qr-expired")).toBeVisible();
    await expect(page.getByTestId("qr")).toHaveCount(0);
    await expect(page.getByTestId("ceiling-remaining")).toBeVisible();
    await expect(page.getByRole("button", { name: fr["card.present"] })).toBeDisabled();

    const stored = await page.evaluate(() => window.localStorage.getItem("mulema.adherent.derniere-carte") ?? "");
    expect(stored).toContain(card.member_number);
    expect(stored).not.toContain("qr_");
    const apiCached = await page.evaluate(async () => {
      const urls: string[] = [];
      for (const key of await caches.keys()) for (const req of await (await caches.open(key)).keys()) urls.push(new URL(req.url).pathname);
      return urls.filter((u) => u.startsWith("/api/") || u.startsWith("/payer/"));
    });
    expect(apiCached, "aucune réponse d'API ni page de paiement dans le cache").toEqual([]);

    const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"]).analyze();
    expect(results.violations.map((v) => v.id)).toEqual([]);
  });
});
