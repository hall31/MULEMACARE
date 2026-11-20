import { expect, test, type Page } from "@playwright/test";
import { contractProblems } from "../src/test/contract-event";
import { MEMBER_NUMBER, MockApi } from "./mock-api";
import { fr, openCounter, selectActs, shot, toActs, toIdentity, tr, xof } from "./flow";

/**
 * Phase 2, voie A — comptoir : aide contextuelle de première utilisation (sobre, non bloquante,
 * désactivable) et bandeau hors ligne qui dit ce qui reste possible et ce qui ne l'est pas.
 */
const HELP_KEY = "mulema.comptoir.aide";

test.describe("aide de première utilisation", () => {
  test("une bulle par écran, non bloquante : le parcours avance sans la fermer", async ({ page }) => {
    const api = new MockApi();
    api.coachMarks = true;
    await openCounter(page, api);
    const coach = page.getByTestId("coach-mark");
    await expect(coach).toHaveAttribute("data-step", "card");
    await expect(coach).toContainText(fr["help.card"]);
    // Aucun voile, aucun focus capturé : le titre de l'écran garde le focus, la saisie reste possible.
    await expect(page.getByRole("heading", { level: 1, name: fr["card.title"] })).toBeFocused();
    await expect(page.getByRole("dialog")).toHaveCount(0);
    await shot(page, "18-aide-premiere-utilisation-carte");

    await toIdentity(page, MEMBER_NUMBER);
    await expect(coach).toHaveAttribute("data-step", "identity");
    await expect(coach).toContainText(fr["help.identity"]);
  });

  test("« Compris » retire l'aide de cet écran seulement, et s'en souvient", async ({ page }) => {
    const api = new MockApi();
    api.coachMarks = true;
    await openCounter(page, api);
    await page.getByTestId("coach-mark").getByRole("button", { name: fr["help.gotIt"] }).click();
    await expect(page.getByTestId("coach-mark")).toHaveCount(0);
    await page.reload();
    await expect(page.getByRole("heading", { level: 1, name: fr["card.title"] })).toBeVisible();
    await expect(page.getByTestId("coach-mark")).toHaveCount(0);
    await toIdentity(page);
    await expect(page.getByTestId("coach-mark")).toHaveAttribute("data-step", "identity");
  });

  test("« Ne plus afficher l'aide » coupe toutes les bulles ; le bouton Aide de la barre les rétablit", async ({ page }) => {
    const api = new MockApi();
    api.coachMarks = true;
    await openCounter(page, api);
    const toggle = page.getByRole("button", { name: fr["bar.help.label"] });
    await expect(toggle).toHaveAttribute("aria-pressed", "true");
    await page.getByRole("button", { name: fr["help.disable"] }).click();
    await expect(page.getByTestId("coach-mark")).toHaveCount(0);
    await expect(toggle).toHaveAttribute("aria-pressed", "false");
    await toActs(page);
    await expect(page.getByTestId("coach-mark")).toHaveCount(0);

    await toggle.click();
    await expect(toggle).toHaveAttribute("aria-pressed", "true");
    await expect(page.getByTestId("coach-mark")).toHaveAttribute("data-step", "acts");
    await shot(page, "19-aide-actes");
    // Sur l'appareil : écrans vus et interrupteur, aucune donnée de patient.
    const stored = (await page.evaluate((key) => window.localStorage.getItem(key), HELP_KEY)) ?? "";
    expect(JSON.parse(stored)).toEqual({ v: 1, off: false, seen: [] });
    expect(stored).not.toMatch(/MC-|Aya|FCFA/);
  });
});

test.describe("hors ligne : possible, impossible", () => {
  test("avant l'identification : identifier un nouvel adhérent est impossible, les accords déjà émis restent valables", async ({ page, context }) => {
    const api = await openCounter(page);
    api.networkDown = true;
    await context.setOffline(true);
    const banner = page.getByTestId("offline-banner");
    await expect(banner.getByTestId("offline-banner-title")).toHaveText(tr("net.offline.identification"));
    await expect(banner.getByTestId("offline-can")).toHaveText(`${fr["net.can.title"]} ${fr["net.can.finish"]}`);
    await expect(banner.getByTestId("offline-cannot")).toHaveText(`${fr["net.cannot.title"]} ${fr["net.cannot.identify"]}`);
    await expect(banner).toContainText(fr["net.can.title"]);
    await expect(banner).toContainText(fr["net.cannot.title"]);
  });

  test("identifié, politique reçue : accord provisoire sous le seuil, valable 2 h ; au-delà, médecin-conseil", async ({ page, context }) => {
    const api = await openCounter(page);
    await toActs(page);
    api.networkDown = true;
    await context.setOffline(true);
    await selectActs(page, ["CS-GEN"]);
    const banner = page.getByTestId("offline-banner");
    await expect(banner.getByTestId("offline-can").first()).toContainText(tr("net.can.provisional", { threshold: xof(50_000), duration: "2 h" }));
    await expect(banner.getByTestId("offline-can").nth(1)).toContainText(fr["net.can.sync"]);
    await expect(banner.getByTestId("offline-cannot").first()).toContainText(tr("net.cannot.above", { threshold: xof(50_000) }));
    await shot(page, "20-hors-ligne-possible-impossible");

    await context.setOffline(false);
    api.networkDown = false;
    await expect(banner).toHaveCount(0);
  });
});

/** Parcours complet jusqu'à la décision (chaque étape mesurable). */
async function toDecision(page: Page): Promise<void> {
  await toActs(page);
  await selectActs(page, ["CS-GEN", "NFS", "ECG"]);
  await page.getByRole("button", { name: fr["acts.submit"] }).click();
  await expect(page.getByRole("heading", { level: 1, name: fr["decision.title.auto"] })).toBeVisible();
}

test.describe("consentement à la mesure (pseudonyme) : désactivée tant que la clinique n'a pas choisi", () => {
  test("sans choix : bulle sobre de premier usage, interrupteur éteint, AUCUNE requête de mesure", async ({ page }) => {
    const api = new MockApi();
    api.measure = "unset";
    await openCounter(page, api);
    const bubble = page.getByRole("region", { name: fr["measure.title"] });
    await expect(bubble).toContainText(fr["measure.text"]);
    await expect(page.getByRole("dialog")).toHaveCount(0);
    await expect(page.getByRole("switch", { name: fr["measure.switch"] })).toHaveAttribute("aria-checked", "false");
    await bubble.getByRole("button", { name: fr["measure.learnMore"] }).click();
    await expect(bubble.getByTestId("measure-details")).toContainText(fr["measure.details.never"]);
    await shot(page, "21-mesure-premier-usage");
    await toDecision(page);
    await page.waitForTimeout(800);
    expect(api.events()).toHaveLength(0);
  });

  test("refusée : AUCUNE requête, et le refus survit au rechargement", async ({ page }) => {
    const api = new MockApi();
    api.measure = "unset";
    await openCounter(page, api);
    await page.getByRole("region", { name: fr["measure.title"] }).getByRole("button", { name: fr["measure.refuse"] }).click();
    await expect(page.getByRole("region", { name: fr["measure.title"] })).toHaveCount(0);
    await page.reload();
    await expect(page.getByRole("heading", { level: 1, name: fr["card.title"] })).toBeVisible();
    await expect(page.getByRole("region", { name: fr["measure.title"] })).toHaveCount(0);
    await expect(page.getByRole("switch", { name: fr["measure.switch"] })).toHaveAttribute("aria-checked", "false");
    await toDecision(page);
    await page.waitForTimeout(800);
    expect(api.events()).toHaveLength(0);
  });

  test("interrupteur de l'écran Carte : activé, des événements partent ; désactivé, plus aucun", async ({ page }) => {
    const api = new MockApi();
    api.measure = "unset";
    await openCounter(page, api);
    const toggle = page.getByRole("switch", { name: fr["measure.switch"] });
    await toggle.click();
    await expect(toggle).toHaveAttribute("aria-checked", "true");
    await expect(page.getByRole("region", { name: fr["measure.title"] })).toHaveCount(0);
    await toDecision(page);
    await expect.poll(() => api.events().map((e) => e.name)).toContain("counter_decision_shown");
    // Patient suivant : retour à l'écran Carte, où l'interrupteur se trouve.
    await page.getByRole("button", { name: fr["decision.next"] }).click();
    await expect(page.getByRole("heading", { level: 1, name: fr["card.title"] })).toBeVisible();
    await toggle.click();
    await expect(toggle).toHaveAttribute("aria-checked", "false");
    const before = api.events().length;
    await toDecision(page);
    await page.waitForTimeout(800);
    expect(api.events()).toHaveLength(before);
  });
});

test.describe("mesure produit du comptoir (recordProductEvent), acceptée", () => {
  const ALLOWED_KEYS = ["duration_ms", "name", "role", "session_id", "step", "surface", "variant"];

  test("décision affichée : variante et durée scan → décision ; aucun numéro ni nom envoyé", async ({ page }) => {
    const granted = new MockApi();
    granted.measure = "granted";
    const api = await openCounter(page, granted);
    await toActs(page);
    await selectActs(page, ["CS-GEN", "NFS", "ECG"]);
    await page.getByRole("button", { name: fr["acts.submit"] }).click();
    await expect(page.getByRole("heading", { level: 1, name: fr["decision.title.auto"] })).toBeVisible();
    await expect.poll(() => api.events().map((e) => e.name)).toContain("counter_decision_shown");
    const shown = api.events().find((e) => e.name === "counter_decision_shown")!;
    expect(shown).toMatchObject({ surface: "comptoir", role: "clinique", variant: "accordee" });
    expect(shown.duration_ms).toEqual(expect.any(Number));
    for (const event of api.events()) {
      expect(Object.keys(event).every((k) => ALLOWED_KEYS.includes(k)), JSON.stringify(event)).toBe(true);
      expect(contractProblems(event), JSON.stringify(event)).toEqual([]);
      expect(JSON.stringify(event)).not.toMatch(/MC-|Aya|FCFA|CS-GEN/);
    }
  });

  test("aide de première utilisation : début, étape comprise", async ({ page }) => {
    const api = new MockApi();
    api.coachMarks = true;
    api.measure = "granted";
    await openCounter(page, api);
    await page.getByTestId("coach-mark").getByRole("button", { name: fr["help.gotIt"] }).click();
    await expect.poll(() => api.events().map((e) => e.name)).toEqual(expect.arrayContaining(["onboarding_started", "onboarding_step"]));
    expect(api.events().find((e) => e.name === "onboarding_step")?.step).toBe(1);
  });

  test("bandeau hors ligne : compté au retour du réseau seulement", async ({ page, context }) => {
    const granted = new MockApi();
    granted.measure = "granted";
    const api = await openCounter(page, granted);
    api.networkDown = true;
    await context.setOffline(true);
    await expect(page.getByTestId("offline-banner")).toBeVisible();
    api.networkDown = false;
    await context.setOffline(false);
    await expect.poll(() => api.events().map((e) => e.name)).toContain("offline_banner_seen");
  });
});
