import { expect, test, type Page } from "@playwright/test";
import { qrModules } from "../src/card/qr-matrix";
import { IDS } from "../src/test/fixtures";
import { EXPIRED_TOKEN, FORBIDDEN_TEXT, PAYMENT_TOKEN, UNKNOWN_TOKEN, fr, h1, openCard, openContributions, openPayment, tr, xof } from "./flow";
import { MockApi, MEMBER_TOKEN } from "./mock-api";

/** Charge utile du dernier QR servi par le mock (relue dans le journal des requêtes : le mock la numérote). */
function payloadOf(index: number, memberNumber = "MC-00928194"): string {
  return `MC1.carte-fictive.${memberNumber}.fenetre-${String(index).padStart(4, "0")}.signature-de-test`;
}

async function qrPath(page: Page, testId = "qr"): Promise<string> {
  return (await page.getByTestId(testId).locator("path.qr-m").getAttribute("d")) ?? "";
}

test.describe("parcours « je présente ma carte »", () => {
  test("carte émeraude, QR réel qui se renouvelle avant expiration, plein écran au comptoir", async ({ page }) => {
    // Plein écran et écran allumé : APIs simulées pour observer les appels (le reste est le code de production).
    await page.addInitScript(() => {
      const calls: string[] = [];
      (window as unknown as { __calls: string[] }).__calls = calls;
      Element.prototype.requestFullscreen = async function requestFullscreen() {
        calls.push("fullscreen");
      };
      Object.defineProperty(Navigator.prototype, "wakeLock", {
        configurable: true,
        value: { request: async () => (calls.push("wakeLock"), { release: async () => void calls.push("release") }) },
      });
    });
    const api = new MockApi();
    api.qrWindowMs = 2_500;
    await openCard(page, api);

    const card = page.getByTestId("member-card");
    await expect(card).toContainText("Awa Koné");
    await expect(page.getByTestId("member-number")).toHaveText("MC-00928194");
    await expect(page.getByTestId("rights")).toHaveText(fr["rights.open"]);
    await expect(page.getByTestId("ceiling-remaining")).toHaveText(new Intl.NumberFormat("fr-FR").format(2_580_000));
    await expect(page.getByTestId("ceiling")).toContainText(tr("percent", { value: 14 }));

    // Le QR affiché encode exactement la dernière charge utile servie par l'API (matrice recalculée ici).
    await expect.poll(async () => (await qrPath(page)) === qrModules(payloadOf(api.count("/v1/me/card"))).path).toBe(true);
    const first = await qrPath(page);

    // Il est redemandé à l'échéance annoncée par le serveur, sans action de l'adhérent.
    const served = api.count("/v1/me/card");
    await expect.poll(() => api.count("/v1/me/card"), { timeout: 8_000 }).toBeGreaterThan(served);
    await expect.poll(async () => (await qrPath(page)) === qrModules(payloadOf(api.count("/v1/me/card"))).path).toBe(true);
    expect(await qrPath(page)).not.toBe(first);
    await expect(card).toHaveAttribute("data-phase", "valide");
    for (const r of api.requests.filter((x) => x.path.startsWith("/v1/me"))) expect(r.headers["authorization"]).toBe(MEMBER_TOKEN);

    // Présenter : plein écran, écran maintenu allumé, QR en grand qui continue de tourner.
    const present = page.getByRole("button", { name: fr["card.present"] });
    await present.click();
    const dialog = page.getByRole("dialog", { name: "Awa Koné" });
    await expect(dialog).toBeVisible();
    await expect(dialog).toContainText(fr["present.instruction"]);
    await expect(dialog.getByRole("button", { name: fr["present.close"] })).toBeFocused();
    await expect.poll(() => page.evaluate(() => (window as unknown as { __calls: string[] }).__calls)).toEqual(expect.arrayContaining(["fullscreen", "wakeLock"]));
    const before = api.count("/v1/me/card");
    await expect.poll(() => api.count("/v1/me/card"), { timeout: 8_000 }).toBeGreaterThan(before);
    await expect.poll(async () => (await qrPath(page, "present-qr")) === qrModules(payloadOf(api.count("/v1/me/card"))).path).toBe(true);

    // Échap ferme, le focus revient au bouton, l'écran peut de nouveau s'éteindre.
    await page.keyboard.press("Escape");
    await expect(dialog).toBeHidden();
    await expect(present).toBeFocused();
    await expect.poll(() => page.evaluate(() => (window as unknown as { __calls: string[] }).__calls)).toContain("release");
    await expect(page.locator("body")).not.toContainText(FORBIDDEN_TEXT);
  });

  test("carte d'un bénéficiaire depuis « Mes bénéficiaires » (person_id du contrat)", async ({ page }) => {
    const api = new MockApi();
    await api.install(page);
    await page.goto("/famille");
    await h1(page, fr["family.title"]);
    await expect(page.getByTestId("beneficiary")).toHaveCount(3);
    await expect(page.getByTestId("beneficiary").nth(2)).toContainText(fr["beneficiary.card.aucune"]);
    await page.getByRole("link", { name: tr("family.showCardOf", { name: "Kouassi Koné" }) }).click();
    await h1(page, fr["card.title.other"]);
    await expect(page.getByTestId("member-number")).toHaveText("MC-00928195");
    expect(api.requests.find((r) => r.path === "/v1/me/card" && r.search.includes("person_id"))?.search).toBe(`?person_id=${IDS.kouassi}`);
  });
});

test.describe("parcours « j'invite un proche à payer »", () => {
  test("crée le lien (clé d'idempotence), puis partage natif, WhatsApp et copie", async ({ page, context }) => {
    await context.grantPermissions(["clipboard-read", "clipboard-write"]);
    await page.addInitScript(() => {
      const shared: ShareData[] = [];
      (window as unknown as { __shared: ShareData[] }).__shared = shared;
      Object.defineProperty(navigator, "share", { configurable: true, value: async (data: ShareData) => void shared.push(data) });
    });
    const api = await openContributions(page);
    const due = page.getByTestId("next-due");
    await expect(due).toContainText(xof(27_500));
    await expect(due).toContainText(tr("contribution.title", { month: "d’octobre" }));
    await expect(due).toContainText(fr["contribution.status.a_payer"]);

    // Première tentative coupée par le réseau : erreur avec son code, nouvel essai avec la MÊME clé.
    const path = `/v1/me/contributions/${IDS.octobre}/payment-links`;
    api.abortOnce.add(path);
    await page.getByRole("button", { name: fr["invite.button"] }).click();
    await expect(page.getByTestId("invite-error")).toHaveAttribute("data-code", "E-NET-02");
    await expect(page.getByTestId("invite-error")).toContainText(tr("error.codeLabel", { code: "E-NET-02" }));
    await page.getByTestId("invite-error").getByRole("button", { name: fr["error.retry"] }).click();
    const link = page.getByTestId("invite-link");
    await expect(link).toBeVisible();
    const posts = api.requests.filter((r) => r.method === "POST" && r.path === path);
    expect(posts).toHaveLength(2);
    expect(posts[0]?.headers["idempotency-key"]).toBeTruthy();
    expect(posts[1]?.headers["idempotency-key"]).toBe(posts[0]?.headers["idempotency-key"]);

    const url = `http://127.0.0.1:3200/payer/${PAYMENT_TOKEN}`;
    await expect(page.getByLabel(fr["invite.linkLabel"])).toHaveValue(url);
    await expect(link).toContainText(tr("invite.until", { date: "08/10/2026" }));

    // Partage natif du téléphone : message complet (période, montant entier, échéance, adresse).
    await page.getByTestId("invite-share").click();
    await expect(page.getByTestId("invite-feedback")).toHaveText(fr["invite.shared"]);
    const shared = await page.evaluate(() => (window as unknown as { __shared: ShareData[] }).__shared);
    expect(shared[0]?.url).toBe(url);
    expect(shared[0]?.text).toContain(xof(27_500));
    expect(shared[0]?.text).toContain("d’octobre 2026");

    // WhatsApp : simple lien wa.me ouvert par l'adhérent, message encodé.
    const whatsapp = new URL((await page.getByTestId("invite-whatsapp").getAttribute("href")) ?? "");
    expect(whatsapp.origin).toBe("https://wa.me");
    expect(whatsapp.searchParams.get("text")).toContain(url);

    // Copie.
    await page.getByTestId("invite-copy").click();
    await expect(page.getByTestId("invite-feedback")).toHaveText(fr["invite.copied"]);
    expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(url);
  });

  test("cotisation déjà réglée : erreur 409 affichée avec son code, sans lien", async ({ page }) => {
    const api = new MockApi();
    api.failures.set(`/v1/me/contributions/${IDS.octobre}/payment-links`, { status: 409, problem: { code: "PAY-02", message: "Cette cotisation est déjà réglée.", action: "Aucun lien n'est nécessaire." } });
    await openContributions(page, api);
    await page.getByRole("button", { name: fr["invite.button"] }).click();
    await expect(page.getByTestId("invite-error")).toHaveAttribute("data-code", "PAY-02");
    await expect(page.getByTestId("invite-error")).toContainText("Cette cotisation est déjà réglée.");
    await expect(page.getByTestId("invite-link")).toHaveCount(0);
  });
});

test.describe("parcours « je suis un remboursement »", () => {
  test("liste, puis frise demande reçue → accordée → virement en cours (sans date) → reçu", async ({ page }) => {
    const api = new MockApi();
    await api.install(page);
    await page.goto("/soins");
    await h1(page, fr["claims.title"]);
    const rows = page.getByTestId("claim-row");
    await expect(rows).toHaveCount(3);
    await expect(rows.first()).toContainText("Pharmacie Riviera 3");
    await expect(rows.first()).toContainText(fr["claim.status.accordee_auto"]);
    await expect(rows.nth(2)).toContainText(fr["claim.status.refusee"]);
    await rows.first().click();

    await h1(page, fr["tracking.title"]);
    await expect(page).toHaveURL(new RegExp(`/soins/${IDS.claimPharmacy}$`));
    await expect(page.locator(".pay-hero .money-display")).toHaveText(xof(13_760));
    const steps = page.getByTestId("timeline").locator("li");
    await expect(steps).toHaveCount(4);
    await expect(steps.nth(0)).toContainText(fr["tracking.step.demande_recue"]);
    await expect(steps.nth(0)).toContainText("28/09 · 14:51");
    await expect(steps.nth(1)).toContainText(fr["tracking.step.accordee.fait"]);
    await expect(steps.nth(1)).toContainText(tr("tracking.rule", { code: "R-12", version: 3 }));
    await expect(steps.nth(2)).toHaveAttribute("data-state", "en_cours");
    await expect(steps.nth(2)).toHaveAttribute("aria-current", "step");
    await expect(steps.nth(2).locator("span").last()).toHaveText(fr["tracking.state.en_cours"]);
    await expect(steps.nth(3)).toContainText(fr["tracking.state.a_venir"]);
    await expect(page.locator("body")).not.toContainText(FORBIDDEN_TEXT);
    expect(api.count(`/v1/me/claims/${IDS.claimPharmacy}/tracking`)).toBe(1);
  });

  test("dossier refusé : cachet critique, code de règle, étapes suivantes sans objet", async ({ page }) => {
    const api = new MockApi();
    await api.install(page);
    await page.goto(`/soins/${IDS.claimRefused}`);
    await h1(page, fr["tracking.title"]);
    const steps = page.getByTestId("timeline").locator("li");
    await expect(steps.nth(1)).toContainText(fr["tracking.step.accordee.refuse"]);
    await expect(steps.nth(1)).toContainText("R-04 v2");
    await expect(steps.nth(2)).toContainText(fr["tracking.state.sans_objet"]);
    await expect(page.getByTestId("claim-status")).toHaveAttribute("data-tone", "crit");
  });
});

test.describe("page publique du lien de paiement diaspora", () => {
  test("sans compte : montant FCFA + équivalent, moyen de paiement, paiement confirmé", async ({ page }) => {
    const api = await openPayment(page);
    await h1(page, tr("pay.title", { period: "d’octobre 2026", initials: "A. K." }));
    const form = page.getByTestId("pay-form");
    await expect(form.locator(".money-display")).toHaveText(xof(27_500));
    await expect(page.getByTestId("pay-equivalent")).toContainText("41,92 €");
    await expect(page.getByTestId("pay-equivalent")).toContainText("655,957 FCFA");
    await expect(form.getByRole("radio")).toHaveCount(2);
    await form.getByRole("radio", { name: /Orange Money/ }).check();
    await page.getByRole("button", { name: tr("pay.submit", { amount: xof(27_500) }) }).click();

    await h1(page, fr["pay.done.title"]);
    await expect(page.getByTestId("pay-done")).toContainText(tr("pay.done.proof", { channel: "Orange Money", reference: "9F8E7D6C" }));
    const checkout = api.requests.find((r) => r.method === "POST" && r.path.endsWith("/checkout"));
    expect(checkout?.body).toEqual({ channel: "orange_money" });
    expect(checkout?.headers["idempotency-key"]).toBeTruthy();
    for (const r of api.requests) expect(r.headers["authorization"], `${r.method} ${r.path}`).toBeUndefined();
    await expect(page.locator("body")).not.toContainText(FORBIDDEN_TEXT);
  });

  test("paiement en attente de validation dans l'application", async ({ page }) => {
    const api = new MockApi();
    api.checkoutStatus = "en_attente";
    await openPayment(page, api);
    await page.getByRole("button", { name: tr("pay.submit", { amount: xof(27_500) }) }).click();
    await expect(page.getByTestId("pay-pending")).toContainText(tr("pay.pending.title"));
    await expect(page.getByTestId("pay-pending")).toContainText("Wave");
  });

  test("lien expiré ou déjà utilisé : 410 PAY-03", async ({ page }) => {
    await openPayment(page, new MockApi(), EXPIRED_TOKEN);
    await h1(page, fr["pay.expired.title"]);
    await expect(page.getByTestId("pay-expired")).toHaveAttribute("data-code", "PAY-03");
    await expect(page.getByTestId("pay-expired")).toContainText("Demandez un nouveau lien");
    await expect(page.getByTestId("pay-form")).toHaveCount(0);
  });

  test("lien inconnu : 404 NOT-01, page « introuvable »", async ({ page }) => {
    await openPayment(page, new MockApi(), UNKNOWN_TOKEN);
    await h1(page, fr["pay.invalid.title"]);
    await expect(page.getByTestId("pay-invalid")).toHaveAttribute("data-code", "NOT-01");
  });
});
