import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { expect, test, type Page } from "@playwright/test";
import { fr, h1, openCard, shot } from "./flow";
import { MockApi } from "./mock-api";
import { SCREENS, type ScreenName } from "./screens";

/**
 * Captures de l'espace adhérent dans `screenshots/` (données fictives), et planches de
 * comparaison avec la direction validée (`specs/design/direction/screenshots`, écrans 03 et 04) :
 * `compare-*.png` met côte à côte la cible et l'application, même largeur, même thème.
 */
const here = path.dirname(fileURLToPath(import.meta.url));
const BOARD = path.join(here, "../../../../specs/design/direction/screenshots");
const OUT = path.join(here, "../screenshots");

test.describe.configure({ mode: "serial" });

const WIDTHS = [375, 768, 1280] as const;
const THEMES = [
  { name: "clair", scheme: "light" },
  { name: "sombre", scheme: "dark" },
] as const;

const MAIN: { prefix: string; screen: ScreenName; board: string }[] = [
  { prefix: "01-carte", screen: "carte", board: "03-espace-adherent-carte" },
  { prefix: "02-paiement", screen: "paiement", board: "04-lien-paiement-diaspora" },
];

async function compare(page: Page, boardFile: string, appFile: string, out: string, width: number): Promise<void> {
  const b64 = (file: string) => readFileSync(file).toString("base64");
  const scale = width >= 1280 ? 0.5 : 1;
  await page.setViewportSize({ width: Math.round(width * scale * 2 + 72), height: 900 });
  await page.setContent(`<!doctype html><html><body style="margin:0;padding:16px;display:flex;gap:40px;align-items:flex-start;font:600 16px system-ui;background:white">
    <figure style="margin:0;width:${width * scale}px"><figcaption style="margin-bottom:8px">Planche (cible) · ${path.basename(boardFile)}</figcaption><img style="width:100%;border:1px solid silver" src="data:image/png;base64,${b64(boardFile)}"></figure>
    <figure style="margin:0;width:${width * scale}px"><figcaption style="margin-bottom:8px">Application · ${path.basename(appFile)}</figcaption><img style="width:100%;border:1px solid silver" src="data:image/png;base64,${b64(appFile)}"></figure>
  </body></html>`);
  await page.waitForFunction(() => [...document.images].every((i) => i.complete));
  await page.screenshot({ path: out, fullPage: true });
}

for (const theme of THEMES) {
  test.describe(`captures principales — ${theme.name}`, () => {
    test.use({ colorScheme: theme.scheme });
    for (const width of WIDTHS) {
      test(`carte et paiement à ${width} px`, async ({ page, context, browser }) => {
        await page.setViewportSize({ width, height: 812 });
        for (const item of MAIN) {
          await SCREENS[item.screen](page, context);
          await page.waitForTimeout(450);
          await shot(page, `${item.prefix}-${width}-${theme.name}`);
          if (theme.name === "clair" && (width === 375 || width === 1280)) {
            const comparePage = await browser.newPage();
            await compare(comparePage, path.join(BOARD, `${item.board}-${width}-${theme.name}.png`), path.join(OUT, `${item.prefix}-${width}-${theme.name}.png`), path.join(OUT, `compare-${item.prefix}-${width}-${theme.name}.png`), width);
            await comparePage.close();
          }
        }
      });
    }
  });
}

const SECONDARY: { file: string; screen: ScreenName; dark?: boolean }[] = [
  { file: "03-presenter-carte-375-clair", screen: "presenter-carte" },
  { file: "03-presenter-carte-375-sombre", screen: "presenter-carte", dark: true },
  { file: "04-soins-375-clair", screen: "soins" },
  { file: "05-suivi-remboursement-375-clair", screen: "suivi" },
  { file: "05-suivi-remboursement-375-sombre", screen: "suivi", dark: true },
  { file: "06-cotisations-375-clair", screen: "cotisations" },
  { file: "07-invitation-creee-375-clair", screen: "invitation-creee" },
  { file: "08-beneficiaires-375-clair", screen: "famille" },
  { file: "09-carte-beneficiaire-375-clair", screen: "carte-beneficiaire" },
  { file: "10-etat-vide-soins-375-clair", screen: "soins-vide" },
  { file: "11-etat-erreur-carte-SYS-01-375-clair", screen: "carte-erreur" },
  { file: "12-etat-qr-expire-hors-ligne-375-clair", screen: "carte-qr-expire" },
  { file: "14-paiement-confirme-375-clair", screen: "paiement-confirme" },
  { file: "15-paiement-expire-PAY-03-375-clair", screen: "paiement-expire" },
  { file: "16-paiement-invalide-NOT-01-375-clair", screen: "paiement-invalide" },
  // Phase 2, voie A : découverte, notifications dérivées, hors ligne.
  { file: "18-premiere-visite-invitation-375-clair", screen: "carte-premiere-visite" },
  { file: "19-decouverte-1-couverture-375-clair", screen: "decouverte-couverture" },
  { file: "19-decouverte-1-couverture-375-sombre", screen: "decouverte-couverture", dark: true },
  { file: "20-decouverte-2-carte-375-clair", screen: "decouverte-carte" },
  { file: "21-decouverte-3-suivi-375-clair", screen: "decouverte-suivi" },
  { file: "22-notifications-375-clair", screen: "notifications" },
  { file: "22-notifications-375-sombre", screen: "notifications", dark: true },
  { file: "23-notifications-vide-375-clair", screen: "notifications-vide" },
  { file: "24-hors-ligne-possible-impossible-375-clair", screen: "hors-ligne-cotisations" },
];

for (const item of SECONDARY) {
  test.describe(item.file, () => {
    test.use({ colorScheme: item.dark ? "dark" : "light" });
    test("capture", async ({ page, context }) => {
      await SCREENS[item.screen](page, context);
      await page.waitForTimeout(450);
      await shot(page, item.file);
    });
  });
}

test("09b — état chargement (squelette après 300 ms)", async ({ page }) => {
  const api = new MockApi();
  api.delays.set("/v1/me/card", 4_000);
  api.delays.set("/v1/me/claims", 4_000);
  api.delays.set("/v1/me/contributions", 4_000);
  await api.install(page);
  await page.goto("/");
  await h1(page, fr["card.title"]);
  await expect(page.getByTestId("card-loading").locator(".sk").first()).toBeVisible();
  await shot(page, "13-etat-chargement-375-clair");
});

test.describe("hors ligne au redémarrage (service worker)", () => {
  test.use({ serviceWorkers: "allow" });
  test("13b — dernière carte enregistrée", async ({ page, context }) => {
    const api = new MockApi();
    await openCard(page, api);
    await page.evaluate(async () => {
      await navigator.serviceWorker.ready;
    });
    await page.reload();
    await expect.poll(() => page.evaluate(() => Boolean(navigator.serviceWorker.controller))).toBe(true);
    api.networkDown = true;
    await context.setOffline(true);
    await page.reload();
    await expect(page.getByTestId("card-offline")).toBeVisible();
    await shot(page, "12b-carte-hors-ligne-enregistree-375-clair");
  });
});

test("17 — carte bloquée (ID-04)", async ({ page }) => {
  const api = new MockApi();
  api.cardPatch = { card_status: "bloquee", blocked_until: "2026-10-01T10:15:00Z" };
  await openCard(page, api);
  await shot(page, "17-carte-bloquee-ID-04-375-clair");
});
