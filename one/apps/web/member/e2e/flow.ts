import { expect, type Page } from "@playwright/test";
import fr from "../src/i18n/fr.json" with { type: "json" };
import { EXPIRED_TOKEN, IDS, PAYMENT_TOKEN, UNKNOWN_TOKEN } from "../src/test/fixtures";
import { MockApi } from "./mock-api";

export { fr };
export type Key = keyof typeof fr;

/** Remplace les {paramètres} d'un texte du fichier de traduction. */
export function tr(key: Key, params: Record<string, string | number> = {}): string {
  return fr[key].replace(/\{(\w+)\}/g, (_, name: string) => String(params[name] ?? `{${name}}`));
}

/** Montant tel qu'affiché (séparateur de milliers fr-FR : espace fine insécable). */
export function xof(amount: number): string {
  return tr("money.xof", { amount: new Intl.NumberFormat("fr-FR").format(amount) });
}

export async function h1(page: Page, name: string | RegExp): Promise<void> {
  await expect(page.getByRole("heading", { level: 1, name })).toBeVisible();
}

export async function openCard(page: Page, api: MockApi = new MockApi()): Promise<MockApi> {
  await api.install(page);
  await page.goto("/");
  await h1(page, fr["card.title"]);
  await expect(page.getByTestId("qr")).toHaveAttribute("data-ready", "true");
  return api;
}

export async function openClaims(page: Page, api: MockApi = new MockApi()): Promise<MockApi> {
  await api.install(page);
  await page.goto("/soins");
  await h1(page, fr["claims.title"]);
  await expect(page.getByTestId("claim-row").first()).toBeVisible();
  return api;
}

export async function openTracking(page: Page, api: MockApi = new MockApi(), claimId: string = IDS.claimPharmacy): Promise<MockApi> {
  await api.install(page);
  await page.goto(`/soins/${claimId}`);
  await h1(page, fr["tracking.title"]);
  await expect(page.getByTestId("timeline")).toBeVisible();
  return api;
}

export async function openContributions(page: Page, api: MockApi = new MockApi()): Promise<MockApi> {
  await api.install(page);
  await page.goto("/cotisations");
  await h1(page, fr["contributions.title"]);
  await expect(page.getByTestId("next-due")).toBeVisible();
  return api;
}

export async function openFamily(page: Page, api: MockApi = new MockApi()): Promise<MockApi> {
  await api.install(page);
  await page.goto("/famille");
  await h1(page, fr["family.title"]);
  await expect(page.getByTestId("beneficiary").first()).toBeVisible();
  return api;
}

export async function openPayment(page: Page, api: MockApi = new MockApi(), token: string = PAYMENT_TOKEN): Promise<MockApi> {
  await api.install(page);
  await page.goto(`/payer/${token}`);
  return api;
}

export { EXPIRED_TOKEN, PAYMENT_TOKEN, UNKNOWN_TOKEN };

/** Aucune donnée médicale, aucun score, aucune règle interne dans le texte affiché. */
export const FORBIDDEN_TEXT = /diagnos|ordonnance|pathologie|motif m[ée]dical|score|fraude|risque|healthos|acte m[ée]dical/i;

/** Capture de tout l'écran (fenêtre agrandie à la hauteur du contenu ; barres collées comprises). */
export async function shot(page: Page, name: string): Promise<void> {
  const viewport = page.viewportSize();
  if (!viewport) throw new Error("viewport inconnu");
  await page.evaluate(() => document.fonts.ready);
  // Plein écran (présenter ma carte) : la fenêtre ne se redimensionne pas, la vue fixe suffit.
  if (await page.evaluate(() => Boolean(document.fullscreenElement))) {
    await page.screenshot({ path: `screenshots/${name}.png`, animations: "disabled" });
    return;
  }
  const height = await page.evaluate(() => document.documentElement.scrollHeight);
  await page.setViewportSize({ width: viewport.width, height: Math.max(height, viewport.height) });
  await page.screenshot({ path: `screenshots/${name}.png`, animations: "disabled" });
  await page.setViewportSize(viewport);
}
