import { expect, test } from "@playwright/test";
import { fr, tr } from "./flow";

test.describe("PWA installable et utilisable sans réseau", () => {
  test.use({ serviceWorkers: "allow" });

  test("manifeste installable", async ({ request }) => {
    const response = await request.get("/manifest.webmanifest");
    expect(response.ok()).toBe(true);
    const manifest = (await response.json()) as Record<string, unknown> & { icons: { sizes: string; purpose?: string; src: string }[] };
    expect(manifest).toMatchObject({ name: fr["app.name"], short_name: fr["app.shortName"], start_url: "/", display: "standalone", lang: "fr" });
    expect(manifest.theme_color).toMatch(/^#[0-9a-f]{6}$/i);
    expect(manifest.icons.map((i) => `${i.sizes}:${i.purpose ?? "any"}`)).toEqual(expect.arrayContaining(["192x192:any", "512x512:any", "512x512:maskable"]));
    for (const icon of manifest.icons) expect((await request.get(icon.src)).headers()["content-type"]).toBe("image/png");
  });

  test("le service worker met l'application en cache : elle redémarre réseau coupé", async ({ page, context }) => {
    await context.route("**/api/v1/**", (route) => route.abort("internetdisconnected"));
    await page.goto("/");
    await expect(page.getByRole("heading", { level: 1, name: fr["card.title"] })).toBeVisible();
    await page.evaluate(async () => {
      await navigator.serviceWorker.ready;
    });
    // Deuxième chargement contrôlé par le service worker : il remplit le cache à l'exécution.
    await page.reload();
    await expect.poll(() => page.evaluate(() => Boolean(navigator.serviceWorker.controller))).toBe(true);
    await expect(page.getByRole("heading", { level: 1, name: fr["card.title"] })).toBeVisible();

    await context.setOffline(true);
    await page.reload();
    await expect(page.getByRole("heading", { level: 1, name: fr["card.title"] })).toBeVisible();
    await expect(page.getByTestId("offline-banner-title")).toHaveText(tr("net.offline.identification"));
    const apiCached = await page.evaluate(async () => {
      const keys = await caches.keys();
      const urls: string[] = [];
      for (const key of keys) for (const req of await (await caches.open(key)).keys()) urls.push(new URL(req.url).pathname);
      return urls.filter((u) => u.startsWith("/api/"));
    });
    expect(apiCached, "aucune réponse d'API dans le cache").toEqual([]);
  });
});
