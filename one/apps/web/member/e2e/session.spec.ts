import { expect, test, type Page } from "@playwright/test";
import { card } from "../src/test/fixtures";
import { fr, h1, openCard, tr, xof } from "./flow";
import { MockApi, type Failure } from "./mock-api";

/**
 * Carte enregistrée sur le téléphone : montrée seulement sur une erreur RÉSEAU, jamais après un
 * refus d'accès (session expirée, carte révoquée), jamais au-delà de 24 h, effacée à la
 * déconnexion. Démonstration du vérificateur : après un 401 AUTH-01 ou un 404 NOT-01 sur
 * /v1/me/card, le nom, le numéro d'adhérent et le plafond restaient lisibles, sans erreur.
 */
const LAST_CARD_KEY = "mulema.adherent.derniere-carte";

const AUTH_01: Failure = { status: 401, problem: { code: "AUTH-01", message: "Votre session a expiré.", action: "Reconnectez-vous puis recommencez." } };
const NOT_01: Failure = { status: 404, problem: { code: "NOT-01", message: "Introuvable.", action: "Vérifiez l'adresse ou revenez à l'accueil." } };
const SYS_01: Failure = { status: 503, problem: { code: "SYS-01", message: "Service momentanément indisponible.", action: "Réessayez dans un instant." } };

const storedCard = (page: Page) => page.evaluate((key) => window.localStorage.getItem(key), LAST_CARD_KEY);

/**
 * Aucune donnée de la carte à l'écran : ni nom, ni numéro d'adhérent, ni plafond restant. `main` :
 * rien de l'adhérent sur tout l'écran (refus d'accès) ; `card` : la colonne de la carte seulement
 * (les autres panneaux, servis normalement, restent affichés).
 */
async function expectNoCardData(page: Page, scope: "main" | "card" = "main"): Promise<void> {
  await expect(page.getByTestId("member-card")).toHaveCount(0);
  await expect(page.getByTestId("card-offline")).toHaveCount(0);
  await expect(page.getByTestId("ceiling-remaining")).toHaveCount(0);
  const region = scope === "main" ? page.locator("main") : page.getByTestId("card-screen").locator(".m-col").first();
  const main = await page.locator("main").innerText();
  expect(main).not.toContain(card.member_number);
  expect(main).not.toContain(xof(card.entitlements.remaining_xof));
  await expect(region).not.toContainText(card.family_name);
  await expect(region).not.toContainText(card.given_name);
}

/** Refus sur tout l'espace (le jeton est le même pour toutes les opérations /v1/me/*). */
function denyAll(api: MockApi, failure: Failure): void {
  for (const path of ["/v1/me", "/v1/me/card", "/v1/me/claims", "/v1/me/contributions", "/v1/me/beneficiaries"]) api.failures.set(path, failure);
}

test.describe("refus d'accès : la carte enregistrée n'est jamais montrée et elle est effacée", () => {
  for (const [name, failure] of [
    ["session expirée (401 AUTH-01)", AUTH_01],
    ["carte révoquée (404 NOT-01)", NOT_01],
  ] as const) {
    test(`${name} au rechargement`, async ({ page }) => {
      const api = await openCard(page);
      expect(await storedCard(page)).toContain(card.member_number);

      denyAll(api, failure);
      await page.reload();
      const error = page.getByTestId("card-error");
      await expect(error).toHaveAttribute("data-code", failure.problem.code);
      await expect(error).toContainText(failure.problem.action);
      await expectNoCardData(page);
      await expect.poll(() => storedCard(page)).toBeNull();
    });
  }

  test("session expirée pendant l'affichage : la carte en direct disparaît au renouvellement du QR", async ({ page }) => {
    const api = new MockApi();
    api.qrWindowMs = 500;
    await openCard(page, api);
    denyAll(api, AUTH_01);
    await expect(page.getByTestId("card-error")).toHaveAttribute("data-code", "AUTH-01", { timeout: 15_000 });
    // Les panneaux chargés avant le refus (dernier soin, cotisation) sont oubliés eux aussi.
    await expect(page.getByTestId("latest-claim")).toHaveCount(0);
    await expectNoCardData(page);
    await expect(page.getByRole("button", { name: fr["card.present"] })).toBeDisabled();
    expect(await storedCard(page)).toBeNull();
  });
});

test.describe("carte enregistrée : seulement sur une erreur réseau, jamais plus de 24 h", () => {
  test("panne du serveur (503 SYS-01) : l'erreur, pas la carte enregistrée", async ({ page }) => {
    const api = await openCard(page);
    api.failures.set("/v1/me/card", SYS_01);
    await page.reload();
    await expect(page.getByTestId("card-error")).toHaveAttribute("data-code", "SYS-01");
    await expectNoCardData(page, "card");
  });

  test("serveur injoignable : la carte enregistrée, datée, QR expiré (E-NET-02)", async ({ page }) => {
    const api = await openCard(page);
    api.networkDown = true;
    await page.reload();
    const offline = page.getByTestId("card-offline");
    await expect(offline).toBeVisible();
    await expect(offline).toContainText(tr("error.codeLabel", { code: "E-NET-02" }));
    await expect(offline).toContainText(tr("card.offline.number", { number: card.member_number }));
    await expect(page.getByTestId("member-card")).toHaveAttribute("data-phase", "expire");
  });

  test("carte enregistrée il y a plus de 24 h : message clair, plus aucune donnée, effacée", async ({ page }) => {
    const api = await openCard(page);
    await page.evaluate((key) => {
      const stored = JSON.parse(window.localStorage.getItem(key) ?? "{}") as { savedAt: string };
      stored.savedAt = new Date(Date.now() - 25 * 60 * 60_000).toISOString();
      window.localStorage.setItem(key, JSON.stringify(stored));
    }, LAST_CARD_KEY);
    api.networkDown = true;
    await page.reload();
    const tooOld = page.getByTestId("card-too-old");
    await expect(tooOld).toBeVisible();
    await expect(tooOld).toContainText(fr["card.tooOld.title"]);
    await expect(tooOld).toContainText(tr("error.codeLabel", { code: "E-NET-02" }));
    await expectNoCardData(page);
    await expect.poll(() => storedCard(page)).toBeNull();
  });
});

test.describe("déconnexion", () => {
  test("efface la carte enregistrée et les caches ; hors ligne ensuite, plus rien à lire", async ({ page }) => {
    const api = await openCard(page);
    // Coquille mise en cache par le service worker (simulée : les tests bloquent le service worker).
    await page.evaluate(async () => {
      await (await caches.open("adherent-v1")).put("/", new Response("coquille"));
    });
    expect(await storedCard(page)).toContain(card.member_number);

    await page.getByRole("button", { name: fr["nav.signOut"] }).click();
    await expect(page).toHaveURL(/\/deconnexion$/);
    await h1(page, fr["signedOut.title"]);
    await expect(page.getByTestId("signed-out")).toHaveAttribute("data-purged", "true");
    expect(await storedCard(page)).toBeNull();
    // Seul reste le choix de mesure (aucune donnée de l'adhérent) : un refus survit à la déconnexion.
    expect(await page.evaluate(() => Object.keys(window.localStorage))).toEqual(["mulema.mesure.adherent"]);
    expect(await page.evaluate(async () => (await caches.keys()).length)).toBe(0);

    api.networkDown = true;
    await page.goto("/");
    await expect(page.getByTestId("card-error")).toHaveAttribute("data-code", "E-NET-02");
    await expectNoCardData(page);
  });

  test("revenir à l'espace après la déconnexion", async ({ page }) => {
    await openCard(page);
    await page.getByRole("button", { name: fr["nav.signOut"] }).click();
    await h1(page, fr["signedOut.title"]);
    await page.getByRole("link", { name: fr["signedOut.back"] }).click();
    await h1(page, fr["card.title"]);
  });
});
