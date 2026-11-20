import { expect, type BrowserContext, type Page } from "@playwright/test";
import { IDS, beneficiaries, claimPharmacy, claims, contributions } from "../src/test/fixtures";
import { EXPIRED_TOKEN, UNKNOWN_TOKEN, fr, h1, openCard, openClaims, openContributions, openFamily, openPayment, openTracking, tr, xof } from "./flow";
import { MockApi } from "./mock-api";

type Opener = (page: Page, context: BrowserContext) => Promise<void>;

/** Date calendaire décalée d'aujourd'hui (Abidjan = UTC) : notifications indépendantes de l'horloge. */
export function dayFromToday(offset: number): string {
  return new Date(Date.now() + offset * 86_400_000).toISOString().slice(0, 10);
}

/** Données qui déclenchent chaque type de notification : échéance dans 3 jours, carte bloquée, couverture finie. */
export function notifyingApi(): MockApi {
  const api = new MockApi();
  const due = { ...contributions.items[0]!, due_on: dayFromToday(3) };
  api.contributionsData = { items: [due, ...contributions.items.slice(1)], next_due: due };
  api.beneficiariesData = {
    items: [
      beneficiaries.items[0]!,
      { ...beneficiaries.items[1]!, card_status: "bloquee" },
      { ...beneficiaries.items[2]!, valid_to: dayFromToday(-2) },
    ],
  };
  return api;
}

/** Ouvre la carte (référence des dossiers posée), puis fait avancer un dossier côté serveur. */
export async function withClaimProgress(page: Page, api: MockApi): Promise<void> {
  await openCard(page, api);
  // Référence posée (empreintes seulement : l'identifiant du dossier n'est jamais gardé en clair).
  await expect.poll(() => page.evaluate(() => (JSON.parse(window.localStorage.getItem("mulema.adherent.notifications") ?? "{}") as { baseline?: { known?: string[] } }).baseline?.known?.length ?? 0)).toBeGreaterThan(0);
  api.claimsData = { items: [{ ...claimPharmacy, status: "payee" }, ...claims.slice(1)], page: { next_cursor: null } };
}

/** Chaque écran et chaque état visible de l'espace adhérent et de la page de paiement. */
const DEFINITIONS = {
  carte: async (page) => {
    await openCard(page);
    await expect(page.getByTestId("latest-claim")).toBeVisible();
    await expect(page.getByTestId("home-contribution")).toBeVisible();
  },
  "presenter-carte": async (page) => {
    await openCard(page);
    await page.getByRole("button", { name: fr["card.present"] }).click();
    await expect(page.getByTestId("present-qr")).toHaveAttribute("data-ready", "true");
  },
  "carte-beneficiaire": async (page) => {
    const api = new MockApi();
    await api.install(page);
    await page.goto(`/carte/${IDS.kouassi}`);
    await h1(page, fr["card.title.other"]);
    await expect(page.getByTestId("qr")).toHaveAttribute("data-ready", "true");
  },
  "carte-qr-expire": async (page, context) => {
    const api = new MockApi();
    api.qrWindowMs = 500;
    await openCard(page, api);
    api.networkDown = true;
    await context.setOffline(true);
    await expect(page.getByTestId("qr-expired-notice")).toBeVisible({ timeout: 15_000 });
  },
  "carte-erreur": async (page) => {
    const api = new MockApi();
    api.failures.set("/v1/me/card", { status: 503, problem: { code: "SYS-01", message: "Service momentanément indisponible.", action: "Réessayez dans un instant." } });
    await api.install(page);
    await page.goto("/");
    await expect(page.getByTestId("card-error")).toBeVisible();
  },
  "carte-trop-ancienne": async (page) => {
    const api = await openCard(page);
    await page.evaluate(() => {
      const key = "mulema.adherent.derniere-carte";
      const stored = JSON.parse(window.localStorage.getItem(key) ?? "{}") as { savedAt: string };
      stored.savedAt = new Date(Date.now() - 25 * 60 * 60_000).toISOString();
      window.localStorage.setItem(key, JSON.stringify(stored));
    });
    api.networkDown = true;
    await page.reload();
    await expect(page.getByTestId("card-too-old")).toBeVisible();
  },
  deconnecte: async (page) => {
    await openCard(page);
    await page.getByRole("button", { name: fr["nav.signOut"] }).click();
    await expect(page.getByTestId("signed-out")).toHaveAttribute("data-purged", "true");
  },
  soins: async (page) => {
    await openClaims(page);
  },
  "soins-vide": async (page) => {
    const api = new MockApi();
    api.claimsData = { items: [], page: { next_cursor: null } };
    await api.install(page);
    await page.goto("/soins");
    await expect(page.getByTestId("empty-state")).toBeVisible();
  },
  suivi: async (page) => {
    await openTracking(page);
  },
  cotisations: async (page) => {
    await openContributions(page);
  },
  "invitation-creee": async (page) => {
    await openContributions(page);
    await page.getByRole("button", { name: fr["invite.button"] }).click();
    await expect(page.getByTestId("invite-link")).toBeVisible();
  },
  famille: async (page) => {
    await openFamily(page);
  },
  "carte-premiere-visite": async (page) => {
    const api = new MockApi();
    api.firstVisit = true;
    await openCard(page, api);
    await expect(page.getByTestId("tour-invite")).toBeVisible();
  },
  "decouverte-couverture": async (page) => {
    const api = new MockApi();
    api.firstVisit = true;
    await api.install(page);
    await page.goto("/decouverte");
    await h1(page, fr["tour.step.couverture.title"]);
    await expect(page.getByTestId("tour-rate")).toBeVisible();
    await page.getByRole("radio", { name: xof(2_000) }).check();
    await expect(page.getByTestId("tour-feedback")).toBeVisible();
  },
  "decouverte-carte": async (page) => {
    const api = new MockApi();
    api.firstVisit = true;
    await api.install(page);
    await page.goto("/decouverte");
    await expect(page.getByTestId("tour-rate")).toBeVisible();
    await page.getByRole("button", { name: fr["tour.next"] }).click();
    await h1(page, fr["tour.step.carte.title"]);
  },
  "decouverte-suivi": async (page) => {
    const api = new MockApi();
    api.firstVisit = true;
    await api.install(page);
    await page.goto("/decouverte");
    await expect(page.getByTestId("tour-rate")).toBeVisible();
    await page.getByRole("button", { name: fr["tour.next"] }).click();
    await page.getByRole("button", { name: fr["tour.next"] }).click();
    await h1(page, fr["tour.step.suivi.title"]);
    await expect(page.getByRole("link", { name: fr["tour.suivi.latest"] })).toBeVisible();
  },
  notifications: async (page) => {
    const api = notifyingApi();
    await withClaimProgress(page, api);
    await page.goto("/notifications");
    await h1(page, fr["notif.title"]);
    await expect(page.getByTestId("notification")).toHaveCount(4);
  },
  "notifications-vide": async (page) => {
    const api = new MockApi();
    api.contributionsData = { items: contributions.items.slice(1), next_due: null };
    await api.install(page);
    await page.goto("/notifications");
    await h1(page, fr["notif.title"]);
    await expect(page.getByTestId("empty-state")).toBeVisible();
  },
  "notifications-preferences": async (page) => {
    await notifyingApi().install(page);
    await page.goto("/notifications");
    await h1(page, fr["notif.title"]);
    await page.getByText(fr["notif.prefs.title"]).click();
    await expect(page.getByRole("switch", { name: fr["notif.prefs.cards"] })).toBeVisible();
    await page.getByRole("switch", { name: fr["notif.prefs.cards"] }).scrollIntoViewIfNeeded();
  },
  "hors-ligne-cotisations": async (page, context) => {
    await openContributions(page);
    await context.setOffline(true);
    await expect(page.getByTestId("offline-banner")).toBeVisible();
    await expect(page.getByTestId("invite-offline")).toBeVisible();
  },
  paiement: async (page) => {
    await openPayment(page);
    await expect(page.getByTestId("pay-form")).toBeVisible();
  },
  "paiement-confirme": async (page) => {
    await openPayment(page);
    await page.getByRole("button", { name: tr("pay.submit", { amount: xof(27_500) }) }).click();
    await expect(page.getByTestId("pay-done")).toBeVisible();
  },
  "paiement-expire": async (page) => {
    await openPayment(page, new MockApi(), EXPIRED_TOKEN);
    await expect(page.getByTestId("pay-expired")).toBeVisible();
  },
  "paiement-invalide": async (page) => {
    await openPayment(page, new MockApi(), UNKNOWN_TOKEN);
    await expect(page.getByTestId("pay-invalid")).toBeVisible();
  },
} satisfies Record<string, Opener>;

export type ScreenName = keyof typeof DEFINITIONS;
export const SCREENS: Record<ScreenName, Opener> = DEFINITIONS;
export const SCREEN_NAMES = Object.keys(SCREENS) as ScreenName[];
