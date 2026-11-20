import { expect, test, type Page } from "@playwright/test";
import { TOUR_KEY } from "../src/onboarding/tour";
import { contractProblems } from "../src/test/contract-event";
import { card, claimPharmacy, contributions } from "../src/test/fixtures";
import { FORBIDDEN_TEXT, fr, h1, openCard, openContributions, tr, xof } from "./flow";
import { MockApi } from "./mock-api";
import { notifyingApi, withClaimProgress } from "./screens";

/**
 * Phase 2, voie A — espace adhérent : découverte sans formation (première visite, trois étapes,
 * passable, rejouable), centre de notifications dérivé des données du contrat (aucun envoi),
 * mode hors ligne (ce qui reste possible, ce qui ne l'est pas).
 */
/** Même valeur que `NOTIFICATIONS_KEY` (src/notifications/derive.ts, qui charge les traductions sans attribut d'import). */
const NOTIFICATIONS_KEY = "mulema.adherent.notifications";
const stored = (page: Page, key: string) => page.evaluate((k) => window.localStorage.getItem(k), key);

test.describe("découverte : première visite", () => {
  test("invitation non bloquante sous la carte, puis les trois étapes jusqu'à « Terminer »", async ({ page }) => {
    const api = new MockApi();
    api.firstVisit = true;
    await openCard(page, api);
    const invite = page.getByTestId("tour-invite");
    await expect(invite).toBeVisible();
    // Non bloquante : la carte et « Présenter ma carte » restent utilisables.
    await expect(page.getByRole("button", { name: fr["card.present"] })).toBeEnabled();
    await invite.getByRole("link", { name: fr["tour.invite.start"] }).click();

    // Étape 1 : couverture tirée de getMyCard (taux, exemple chiffré, plafond, droits).
    await h1(page, fr["tour.step.couverture.title"]);
    await expect(page.getByText(tr("tour.eyebrow", { n: 1, total: 3 }))).toBeVisible();
    await expect(page.getByTestId("tour-rate")).toHaveText(tr("percent", { value: 80 }));
    await expect(page.getByTestId("tour-example")).toHaveText(tr("tour.couverture.example", { total: xof(10_000), covered: xof(8_000), patient: xof(2_000) }));
    await expect(page.getByTestId("tour-ceiling")).toHaveText(tr("tour.couverture.ceiling", { ceiling: xof(3_000_000), remaining: xof(2_580_000) }));
    await expect(page.getByTestId("tour-rights")).toHaveText(fr["rights.open"]);
    // Vérification de compréhension : une mauvaise réponse est corrigée, la bonne confirmée.
    await page.getByRole("radio", { name: xof(8_000) }).check();
    await expect(page.getByTestId("tour-feedback")).toHaveAttribute("data-correct", "false");
    await page.getByRole("radio", { name: xof(2_000) }).check();
    await expect(page.getByTestId("tour-feedback")).toHaveAttribute("data-correct", "true");
    await expect(page.getByTestId("tour-feedback")).toHaveText(tr("tour.check.right", { patient: xof(2_000) }));

    // Étape 2 : le titre reprend le focus (annoncé par les lecteurs d'écran).
    await page.getByRole("button", { name: fr["tour.next"] }).click();
    await h1(page, fr["tour.step.carte.title"]);
    await expect(page.getByRole("heading", { level: 1 })).toBeFocused();
    await expect(page.getByTestId("tour-present")).toContainText(tr("tour.carte.offline", { number: card.member_number }));

    // Étape 3 : la frise et le dernier remboursement.
    await page.getByRole("button", { name: fr["tour.next"] }).click();
    await h1(page, fr["tour.step.suivi.title"]);
    await expect(page.getByRole("link", { name: fr["tour.suivi.latest"] })).toHaveAttribute("href", `/soins/${claimPharmacy.id}`);
    await page.getByRole("button", { name: fr["tour.prev"] }).click();
    await h1(page, fr["tour.step.carte.title"]);
    await page.getByRole("button", { name: fr["tour.next"] }).click();
    await page.getByRole("button", { name: fr["tour.finish"] }).click();

    await h1(page, fr["card.title"]);
    await expect(page.getByTestId("tour-invite")).toHaveCount(0);
    await expect(page.getByTestId("tour-replay")).toBeVisible();
    const record = JSON.parse((await stored(page, TOUR_KEY)) ?? "{}") as Record<string, unknown>;
    expect(Object.keys(record).sort()).toEqual(["at", "state", "v"]);
    expect(record.state).toBe("termine");
    expect(JSON.stringify(record)).not.toContain(card.member_number);
  });

  test("passable à tout moment et rejouable depuis « Ma carte »", async ({ page }) => {
    const api = new MockApi();
    api.firstVisit = true;
    await openCard(page, api);
    await page.getByTestId("tour-start").click();
    await page.getByRole("button", { name: fr["tour.next"] }).click();
    await page.getByRole("button", { name: fr["tour.skip"] }).click();
    await h1(page, fr["card.title"]);
    expect(JSON.parse((await stored(page, TOUR_KEY)) ?? "{}")).toMatchObject({ state: "passe" });

    await page.reload();
    await h1(page, fr["card.title"]);
    await expect(page.getByTestId("tour-invite")).toHaveCount(0);
    await page.getByRole("link", { name: fr["tour.replay"] }).click();
    await h1(page, fr["tour.step.couverture.title"]);
  });

  test("« Plus tard » : l'invitation disparaît et ne revient pas au rechargement", async ({ page }) => {
    const api = new MockApi();
    api.firstVisit = true;
    await openCard(page, api);
    await page.getByTestId("tour-invite").getByRole("button", { name: fr["tour.invite.later"] }).click();
    await expect(page.getByTestId("tour-invite")).toHaveCount(0);
    await expect(page.getByTestId("tour-replay")).toBeVisible();
    await page.reload();
    await h1(page, fr["card.title"]);
    await expect(page.getByTestId("tour-replay")).toBeVisible();
    await expect(page.getByTestId("tour-invite")).toHaveCount(0);
  });

  test("hors ligne : l'étape 1 reste lisible depuis la carte enregistrée ; erreur serveur : code et Réessayer", async ({ page }) => {
    const api = await openCard(page);
    api.networkDown = true;
    await page.goto("/decouverte");
    await expect(page.getByTestId("tour-saved")).toBeVisible();
    await expect(page.getByTestId("tour-rate")).toHaveText(tr("percent", { value: 80 }));

    api.networkDown = false;
    api.failures.set("/v1/me/card", { status: 503, problem: { code: "SYS-01", message: "Service momentanément indisponible.", action: "Réessayez dans un instant." }, once: true });
    await page.evaluate(() => window.localStorage.clear());
    await page.goto("/decouverte");
    const error = page.getByTestId("tour-error");
    await expect(error).toHaveAttribute("data-code", "SYS-01");
    await error.getByRole("button", { name: fr["error.retry"] }).click();
    await expect(page.getByTestId("tour-rate")).toBeVisible();
  });

  test("aucune donnée médicale dans la découverte", async ({ page }) => {
    const api = new MockApi();
    api.firstVisit = true;
    await api.install(page);
    await page.goto("/decouverte");
    for (let i = 0; i < 3; i += 1) {
      await expect(page.getByTestId("tour")).toBeVisible();
      await expect(page.locator("body")).not.toContainText(FORBIDDEN_TEXT);
      if (i < 2) await page.getByRole("button", { name: fr["tour.next"] }).click();
    }
  });
});

test.describe("centre de notifications dérivé (aucun envoi)", () => {
  test("échéance proche, dossier passé à l'étape suivante, carte bloquée, couverture terminée", async ({ page }) => {
    const api = notifyingApi();
    await withClaimProgress(page, api);
    await page.goto("/notifications");
    await h1(page, fr["notif.title"]);
    const items = page.getByTestId("notification");
    await expect(items).toHaveCount(4);
    // Les critiques d'abord : carte bloquée, couverture terminée ; puis l'échéance (attention).
    await expect(items.nth(0)).toHaveAttribute("data-tone", "crit");
    await expect(page.locator('[data-kind="contribution-due"]')).toContainText(tr("notif.contribution-due.title", { month: "d’octobre" }));
    await expect(page.locator('[data-kind="claim-progress"]')).toContainText(tr("notif.claim-progress.title", { number: claimPharmacy.claim_number, status: fr["claim.status.payee"] }));
    await expect(page.locator('[data-kind="card-blocked"]')).toContainText(tr("notif.card-blocked.title", { name: "Kouassi" }));
    await expect(page.locator('[data-kind="card-expired"]')).toContainText(tr("notif.card-expired.title", { name: "Aya" }));
    await expect(page.getByTestId("notification-bell")).toHaveAttribute("data-unread", "4");
    await expect(page.getByTestId("notification-bell")).toHaveAccessibleName(tr("nav.notifications.unread.other", { count: 4 }));
    await expect(page.locator("body")).not.toContainText(FORBIDDEN_TEXT);
    // Calculé sur le téléphone : aucune commande envoyée (ni SMS, ni WhatsApp, ni autre écriture).
    expect(api.requests.filter((r) => r.method !== "GET" && r.path !== "/v1/telemetry/events")).toEqual([]);

    // Le lien mène au suivi du dossier.
    await page.locator('[data-kind="claim-progress"]').getByRole("link").click();
    await expect(page).toHaveURL(new RegExp(`/soins/${claimPharmacy.id}$`));
  });

  test("tout marquer comme lu : la cloche se vide, l'étape lue disparaît, l'état persistant reste listé", async ({ page }) => {
    const api = notifyingApi();
    await withClaimProgress(page, api);
    await page.goto("/notifications");
    await expect(page.getByTestId("notification")).toHaveCount(4);
    await page.getByRole("button", { name: fr["notif.markAll"] }).click();
    await expect(page.getByTestId("notification-bell")).toHaveAttribute("data-unread", "0");
    await expect(page.getByText(fr["notif.allRead"])).toBeVisible();
    await page.reload();
    await expect(page.getByTestId("notification")).toHaveCount(3);
    await expect(page.locator('[data-kind="claim-progress"]')).toHaveCount(0);
    await expect(page.locator("[data-testid=notification][data-unread]")).toHaveCount(0);
    // Stockage local : empreintes et préférences seulement ; ni identifiant, ni statut, ni nom, ni montant.
    const raw = (await stored(page, NOTIFICATIONS_KEY)) ?? "";
    expect(raw).not.toMatch(/Awa|Kouassi|Pharmacie|MC-|PEC-|FCFA/);
    expect(raw).not.toContain(claimPharmacy.id);
    expect(raw).not.toMatch(/payee|accordee|refusee|en_revue|a_payer|en_retard|bloquee|claim:|card:|contribution:/);
  });

  test("préférences locales : une catégorie désactivée disparaît, le choix survit au rechargement", async ({ page }) => {
    const api = notifyingApi();
    await api.install(page);
    await page.goto("/notifications");
    await expect(page.locator('[data-kind="contribution-due"]')).toHaveCount(1);
    await page.getByText(fr["notif.prefs.title"]).click();
    const pref = page.getByRole("switch", { name: fr["notif.prefs.contributions"] });
    await expect(pref).toHaveAttribute("aria-checked", "true");
    await pref.click();
    await expect(pref).toHaveAttribute("aria-checked", "false");
    await expect(page.locator('[data-kind="contribution-due"]')).toHaveCount(0);
    await page.reload();
    await page.getByText(fr["notif.prefs.title"]).click();
    await expect(page.getByRole("switch", { name: fr["notif.prefs.contributions"] })).toHaveAttribute("aria-checked", "false");
    await expect(page.locator('[data-kind="contribution-due"]')).toHaveCount(0);
    // Délai d'alerte : à 3 jours, une échéance à 3 jours reste signalée.
    await page.getByRole("switch", { name: fr["notif.prefs.contributions"] }).click();
    await page.getByLabel(fr["notif.prefs.leadDays"]).selectOption("3");
    await expect(page.locator('[data-kind="contribution-due"]')).toHaveCount(1);
  });

  test("états : vide guidé, chargement, erreur avec code et Réessayer", async ({ page }) => {
    const api = new MockApi();
    api.contributionsData = { items: contributions.items.slice(1), next_due: null };
    for (const path of ["/v1/me/contributions", "/v1/me/claims", "/v1/me/beneficiaries"]) {
      api.failures.set(path, { status: 503, problem: { code: "SYS-01", message: "Service momentanément indisponible.", action: "Réessayez dans un instant." }, once: true });
    }
    await api.install(page);
    await page.goto("/notifications");
    const error = page.getByTestId("notifications-error");
    await expect(error).toHaveAttribute("data-code", "SYS-01");
    await error.getByRole("button", { name: fr["error.retry"] }).click();
    await expect(page.getByTestId("empty-state")).toContainText(fr["notif.empty.title"]);
    await expect(page.getByTestId("empty-state")).toContainText(fr["notif.empty.text"]);
  });
});

test.describe("hors ligne : ce qui reste possible, ce qui ne l'est pas", () => {
  test("bandeau persistant et action réseau désactivée avec son explication", async ({ page, context }) => {
    await openContributions(page);
    await context.setOffline(true);
    const banner = page.getByTestId("offline-banner");
    await expect(banner).toContainText(fr["net.offline"]);
    await expect(banner.getByTestId("offline-can")).toHaveText(fr["net.offline.can"]);
    await expect(banner.getByTestId("offline-cannot")).toHaveText(fr["net.offline.cannot"]);
    const invite = page.getByRole("button", { name: fr["invite.button"] });
    await expect(invite).toBeDisabled();
    await expect(invite).toHaveAccessibleDescription(fr["invite.offline"]);

    await context.setOffline(false);
    await expect(banner).toHaveCount(0);
  });

  test("notifications : calculées sur les données déjà chargées quand le réseau tombe", async ({ page, context }) => {
    const api = notifyingApi();
    await api.install(page);
    await page.goto("/notifications");
    await expect(page.locator('[data-kind="contribution-due"]')).toHaveCount(1);
    api.networkDown = true;
    await context.setOffline(true);
    await expect(page.getByTestId("notifications-offline")).toBeVisible();
    await expect(page.locator('[data-kind="contribution-due"]')).toHaveCount(1);
  });
});

test.describe("mesure produit (recordProductEvent) : consentement d'abord, liste blanche, sans texte libre", () => {
  const ALLOWED_KEYS = ["duration_ms", "name", "role", "session_id", "step", "surface", "variant"];

  test("découverte : début, étapes, fin ; aucun texte ni identifiant de personne", async ({ page }) => {
    const api = new MockApi();
    api.firstVisit = true;
    api.measure = "granted";
    await api.install(page);
    await page.goto("/decouverte");
    await expect(page.getByTestId("tour-rate")).toBeVisible();
    await page.getByRole("radio", { name: xof(2_000) }).check();
    await page.getByRole("button", { name: fr["tour.next"] }).click();
    await page.getByRole("button", { name: fr["tour.next"] }).click();
    await page.getByRole("button", { name: fr["tour.finish"] }).click();
    await h1(page, fr["card.title"]);
    await expect.poll(() => api.events().map((e) => e.name)).toEqual(expect.arrayContaining(["onboarding_started", "onboarding_step", "onboarding_completed"]));
    const steps = api.events().filter((e) => e.name === "onboarding_step").map((e) => e.step);
    expect(new Set(steps)).toEqual(new Set([1, 2, 3]));
    for (const event of api.events()) {
      expect(Object.keys(event).every((k) => ALLOWED_KEYS.includes(k)), JSON.stringify(event)).toBe(true);
      expect(event).toMatchObject({ surface: "espace_adherent", role: "adherent" });
      expect(String(event.session_id)).toMatch(/^[0-9a-f]{32}$/);
      expect(contractProblems(event), JSON.stringify(event)).toEqual([]);
      expect(JSON.stringify(event)).not.toMatch(/MC-|PEC-|Awa|FCFA|2\s?000/);
    }
    expect(api.events().find((e) => e.name === "onboarding_completed")?.duration_ms).toEqual(expect.any(Number));
  });

  test("carte présentée, suivi consulté, notification ouverte", async ({ page }) => {
    const granted = new MockApi();
    granted.measure = "granted";
    const api = await openCard(page, granted);
    await page.getByRole("button", { name: fr["card.present"] }).click();
    await expect.poll(() => api.events().map((e) => e.name)).toContain("card_presented");
    expect(api.events().find((e) => e.name === "card_presented")?.variant).toBe("en_ligne");
    await page.goto(`/soins/${claimPharmacy.id}`);
    await h1(page, fr["tracking.title"]);
    await expect.poll(() => api.events().map((e) => e.name)).toContain("claim_tracking_viewed");
  });

  test("hors ligne : le bandeau vu est compté au retour du réseau, rien ne part pendant la coupure", async ({ page, context }) => {
    const granted = new MockApi();
    granted.measure = "granted";
    const api = await openContributions(page, granted);
    api.networkDown = true;
    await context.setOffline(true);
    await expect(page.getByTestId("offline-banner")).toBeVisible();
    expect(api.events().map((e) => e.name)).not.toContain("offline_banner_seen");
    api.networkDown = false;
    await context.setOffline(false);
    await expect.poll(() => api.events().map((e) => e.name)).toContain("offline_banner_seen");
  });

  test("sans choix : bandeau sobre de premier usage, mesure désactivée, AUCUNE requête de mesure", async ({ page }) => {
    const api = new MockApi();
    api.measure = "unset";
    await openCard(page, api);
    const banner = page.getByRole("region", { name: fr["measure.title"] });
    await expect(banner).toContainText(fr["measure.text"]);
    await expect(page.getByRole("dialog")).toHaveCount(0);
    await banner.getByRole("button", { name: fr["measure.learnMore"] }).click();
    await expect(banner.getByTestId("measure-details")).toContainText(fr["measure.details.pseudonymous"]);
    await page.getByRole("button", { name: fr["card.present"] }).click();
    await page.goto(`/soins/${claimPharmacy.id}`);
    await h1(page, fr["tracking.title"]);
    await page.goto("/notifications");
    await h1(page, fr["notif.title"]);
    await page.getByText(fr["notif.prefs.title"]).click();
    await expect(page.getByRole("switch", { name: fr["notif.prefs.measure"] })).toHaveAttribute("aria-checked", "false");
    await page.waitForTimeout(800);
    expect(api.events()).toHaveLength(0);
  });

  test("refusée : AUCUNE requête, et le refus survit à la déconnexion", async ({ page }) => {
    const api = new MockApi();
    api.measure = "unset";
    await openCard(page, api);
    await page.getByRole("region", { name: fr["measure.title"] }).getByRole("button", { name: fr["measure.refuse"] }).click();
    await expect(page.getByRole("region", { name: fr["measure.title"] })).toHaveCount(0);
    await page.getByRole("button", { name: fr["nav.signOut"] }).click();
    await h1(page, fr["signedOut.title"]);
    await expect(page.getByTestId("signed-out")).toHaveAttribute("data-purged", "true");
    await page.getByRole("link", { name: fr["signedOut.back"] }).click();
    await h1(page, fr["card.title"]);
    await expect(page.getByRole("region", { name: fr["measure.title"] })).toHaveCount(0);
    await page.getByRole("button", { name: fr["card.present"] }).click();
    await page.goto(`/soins/${claimPharmacy.id}`);
    await h1(page, fr["tracking.title"]);
    await page.waitForTimeout(800);
    expect(api.events()).toHaveLength(0);
  });

  test("interrupteur des préférences : activé, des événements partent ; désactivé, plus aucun", async ({ page }) => {
    const api = new MockApi();
    api.measure = "unset";
    await api.install(page);
    await page.goto("/notifications");
    await h1(page, fr["notif.title"]);
    await page.getByText(fr["notif.prefs.title"]).click();
    const measure = page.getByRole("switch", { name: fr["notif.prefs.measure"] });
    await expect(measure).toHaveAttribute("aria-checked", "false");
    await measure.click();
    await expect(measure).toHaveAttribute("aria-checked", "true");
    await expect(page.getByRole("region", { name: fr["measure.title"] })).toHaveCount(0);
    await page.goto(`/soins/${claimPharmacy.id}`);
    await h1(page, fr["tracking.title"]);
    await expect.poll(() => api.events().map((e) => e.name)).toContain("claim_tracking_viewed");
    await page.goto("/notifications");
    await page.getByText(fr["notif.prefs.title"]).click();
    await page.getByRole("switch", { name: fr["notif.prefs.measure"] }).click();
    await expect(page.getByRole("switch", { name: fr["notif.prefs.measure"] })).toHaveAttribute("aria-checked", "false");
    const before = api.events().length;
    await page.goto("/decouverte");
    await expect(page.getByTestId("tour-rate")).toBeVisible();
    await page.getByRole("button", { name: fr["tour.next"] }).click();
    await page.waitForTimeout(500);
    expect(api.events().length).toBe(before);
  });
});
