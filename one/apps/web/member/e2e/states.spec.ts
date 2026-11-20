import { expect, test } from "@playwright/test";
import { card, claimClinic, claimPharmacy, claimRefused, contributions, IDS } from "../src/test/fixtures";
import { fr, h1, openCard, openContributions, tr } from "./flow";
import { MockApi } from "./mock-api";

/** États obligatoires (contrat §8) : chargement, vide, erreur avec code stable, hors ligne. */
test.describe("chargement", () => {
  test("squelette à la forme du contenu, seulement après 300 ms", async ({ page }) => {
    const api = new MockApi();
    api.delays.set("/v1/me/card", 2_500);
    api.delays.set("/v1/me/claims", 2_500);
    await api.install(page);
    await page.goto("/");
    await h1(page, fr["card.title"]);
    const skeleton = page.getByTestId("card-loading");
    await expect(skeleton).toBeVisible();
    await expect(skeleton.locator(".sk").first()).toBeVisible();
    await expect(page.getByRole("button", { name: fr["card.present"] })).toBeDisabled();
    const reserved = (await skeleton.boundingBox())?.height ?? 0;
    const buttonTop = (await page.getByRole("button", { name: fr["card.present"] }).boundingBox())?.y ?? 0;
    await expect(page.getByTestId("member-card")).toBeVisible({ timeout: 10_000 });
    // Même hauteur que la carte : rien ne saute quand elle arrive (CLS).
    expect(Math.abs(((await page.getByTestId("member-card").boundingBox())?.height ?? 0) - reserved)).toBeLessThanOrEqual(2);
    expect(Math.abs(((await page.getByRole("button", { name: fr["card.present"] }).boundingBox())?.y ?? 0) - buttonTop)).toBeLessThanOrEqual(2);
    await expect(page.getByRole("button", { name: fr["card.present"] })).toBeEnabled();
  });
});

test.describe("vide", () => {
  test("aucun soin : cachet en contour et ce qui arrivera", async ({ page }) => {
    const api = new MockApi();
    api.claimsData = { items: [], page: { next_cursor: null } };
    await api.install(page);
    await page.goto("/soins");
    await expect(page.getByTestId("empty-state")).toContainText(fr["claims.empty.title"]);
    await expect(page.getByTestId("empty-state")).toContainText(fr["claims.empty.text"]);
  });

  test("cotisations à jour : pas d'invitation possible, cachet ok", async ({ page }) => {
    const api = new MockApi();
    const paid = contributions.items.filter((c) => c.status === "payee");
    api.contributionsData = { items: paid, next_due: null };
    await api.install(page);
    await page.goto("/cotisations");
    await expect(page.getByTestId("up-to-date")).toContainText(fr["contributions.upToDate.title"]);
    await expect(page.getByRole("button", { name: fr["invite.button"] })).toHaveCount(0);
    await expect(page.getByTestId("contribution-history").locator("li")).toHaveCount(2);
    await expect(page.getByTestId("contribution-history")).toContainText(tr("contribution.payer.procheFrom", { country: "France" }));
  });
});

test.describe("erreurs : ce qui s'est passé, quoi faire, code stable, Réessayer", () => {
  test("carte indisponible (503 SYS-01) puis rétablie au nouvel essai", async ({ page }) => {
    const api = new MockApi();
    api.failures.set("/v1/me/card", { status: 503, problem: { code: "SYS-01", message: "Service momentanément indisponible.", action: "Réessayez dans un instant." }, once: true });
    await api.install(page);
    await page.goto("/");
    const error = page.getByTestId("card-error");
    await expect(error).toHaveAttribute("data-code", "SYS-01");
    await expect(error).toContainText(fr["error.title.card"]);
    await expect(error).toContainText("Réessayez dans un instant.");
    await expect(error).toContainText(tr("error.codeLabel", { code: "SYS-01" }));
    await error.getByRole("button", { name: fr["error.retry"] }).click();
    await expect(page.getByTestId("member-card")).toBeVisible();
  });

  test("session expirée : AUTH-01 affiché tel que renvoyé par l'API", async ({ page }) => {
    const api = new MockApi();
    api.failures.set("/v1/me/claims", { status: 401, problem: { code: "AUTH-01", message: "Votre session a expiré.", action: "Reconnectez-vous puis recommencez." } });
    await api.install(page);
    await page.goto("/soins");
    await expect(page.getByTestId("error-state")).toHaveAttribute("data-code", "AUTH-01");
    await expect(page.getByTestId("error-state")).toContainText("Reconnectez-vous");
  });

  test("dossier hors de mon contrat : 404 NOT-01 (on ne dit pas pourquoi)", async ({ page }) => {
    const api = new MockApi();
    await api.install(page);
    await page.goto("/soins/00000000-0000-4000-8000-000000000000");
    await expect(page.getByTestId("error-state")).toHaveAttribute("data-code", "NOT-01");
  });

  test("serveur injoignable : E-NET-02 et nouvel essai", async ({ page }) => {
    const api = new MockApi();
    api.abortOnce.add("/v1/me/beneficiaries");
    await api.install(page);
    await page.goto("/famille");
    await expect(page.getByTestId("error-state")).toHaveAttribute("data-code", "E-NET-02");
    await page.getByRole("button", { name: fr["error.retry"] }).click();
    await expect(page.getByTestId("beneficiary")).toHaveCount(3);
  });
});

test.describe("droits et carte", () => {
  test("carte bloquée après trois codes faux : ID-04, présentation impossible", async ({ page }) => {
    const api = new MockApi();
    api.cardPatch = { card_status: "bloquee", blocked_until: "2026-10-01T10:15:00Z" };
    await openCard(page, api);
    await expect(page.getByTestId("rights")).toHaveText(fr["rights.blocked"]);
    await expect(page.getByTestId("card-blocked")).toContainText(tr("card.blocked.title", { time: "10:15" }));
    await expect(page.getByTestId("card-blocked")).toContainText(tr("error.codeLabel", { code: "ID-04" }));
    await expect(page.getByRole("button", { name: fr["card.present"] })).toBeDisabled();
  });

  test("droits suspendus : statut critique et code R-01, jamais la couleur seule", async ({ page }) => {
    const api = new MockApi();
    api.cardPatch = { entitlements: { ...card.entitlements, status: "suspendu", rights_open: false } };
    await openCard(page, api);
    await expect(page.getByTestId("rights")).toHaveText(fr["rights.suspended"]);
    await expect(page.getByTestId("rights-notice")).toContainText(tr("error.codeLabel", { code: "R-01" }));
  });
});

test.describe("hors ligne", () => {
  test("le QR expire clairement quand le réseau manque, bandeau persistant, code E-NET-01", async ({ page, context }) => {
    const api = new MockApi();
    api.qrWindowMs = 500;
    await openCard(page, api);
    api.networkDown = true;
    await context.setOffline(true);
    await expect(page.getByTestId("offline-banner")).toContainText(fr["net.offline"]);
    // Valide jusqu'à l'échéance + 10 s de marge (fenêtre de tolérance du serveur), puis expiré.
    await expect(page.getByTestId("qr-expired")).toBeVisible({ timeout: 15_000 });
    await expect(page.getByTestId("member-card")).toHaveAttribute("data-phase", "expire");
    await expect(page.getByTestId("qr-expired-notice")).toContainText(tr("error.codeLabel", { code: "E-NET-01" }));
    await expect(page.getByTestId("qr-expired-notice")).toContainText("MC-00928194");
    await expect(page.getByRole("button", { name: fr["card.present"] })).toBeDisabled();

    // Retour du réseau : nouveau QR sans action de l'adhérent.
    api.networkDown = false;
    await context.setOffline(false);
    await expect(page.getByTestId("qr")).toBeVisible({ timeout: 15_000 });
    await expect(page.getByTestId("offline-banner")).toHaveCount(0);
    await expect(page.getByRole("button", { name: fr["card.present"] })).toBeEnabled();
  });
});

test.describe("liste paginée", () => {
  test("« Afficher les plus anciennes » suit le curseur du contrat", async ({ page }) => {
    const api = new MockApi();
    await api.install(page);
    await page.route("**/api/v1/me/claims*", async (route) => {
      const cursor = new URL(route.request().url()).searchParams.get("cursor");
      const body = cursor === "page-2" ? { items: [claimRefused], page: { next_cursor: null } } : { items: [claimPharmacy, claimClinic], page: { next_cursor: "page-2" } };
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) });
    });
    await page.goto("/soins");
    await expect(page.getByTestId("claim-row")).toHaveCount(2);
    await page.getByRole("button", { name: fr["claims.more"] }).click();
    await expect(page.getByTestId("claim-row")).toHaveCount(3);
    await expect(page.getByRole("button", { name: fr["claims.more"] })).toHaveCount(0);
  });
});

test("invitation : un clic, un seul lien créé (bouton désactivé pendant l'envoi)", async ({ page }) => {
  const api = await openContributions(page);
  await page.getByRole("button", { name: fr["invite.button"] }).click();
  await expect(page.getByTestId("invite-link")).toBeVisible();
  expect(api.requests.filter((r) => r.method === "POST" && r.path === `/v1/me/contributions/${IDS.octobre}/payment-links`)).toHaveLength(1);
});
