import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import { t } from "../../src/i18n";
import { DEMO_CLAIM_DETAILS, REVIEW_CLAIM, medicalReasonFor } from "../../src/mocks/fixtures";
import { contractProblems } from "../contract-event";
import { MEASURE_CHOICE_KEY, openAs, shot } from "./helpers";

/**
 * Phase 2, voie A — console : palette ⌘K / Ctrl+K (recherche, JOE avec sources, brouillon de
 * décision jamais appliqué), états vides guidés, page « Mesure » (k-anonymat), mesure produit.
 */
async function expectNoA11yViolations(page: Page): Promise<void> {
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"]).analyze();
  const serious = results.violations.filter((v) => v.impact === "moderate" || v.impact === "serious" || v.impact === "critical");
  expect(serious.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(", ")}`)).toEqual([]);
}

const MEDICAL = DEMO_CLAIM_DETAILS.map((d) => medicalReasonFor(d.claim.id));

async function openPalette(page: Page) {
  await page.keyboard.press("Control+k");
  const dialog = page.getByRole("dialog", { name: t("palette.title") });
  await expect(dialog).toBeVisible();
  const input = dialog.getByRole("combobox", { name: t("palette.inputLabel") });
  await expect(input).toBeFocused();
  return { dialog, input };
}

test("palette : Ctrl+K, recherche au clavier, Entrée ouvre le dossier ; Échap ferme", async ({ page }) => {
  await openAs(page, "gestionnaire");
  const { dialog, input } = await openPalette(page);
  await input.fill(REVIEW_CLAIM.claim_number);
  const option = dialog.getByRole("option", { name: new RegExp(REVIEW_CLAIM.claim_number) }).last();
  await expect(option).toBeVisible();
  await expectNoA11yViolations(page);
  await shot(page, "10-palette-recherche");
  await input.press("ArrowDown");
  await expect(input).toHaveAttribute("aria-activedescendant", (await option.getAttribute("id")) ?? "");
  await input.press("Enter");
  await expect(page.getByRole("dialog", { name: t("claim.drawerLabel", { number: REVIEW_CLAIM.claim_number }) })).toBeVisible();

  await page.keyboard.press("Escape");
  await openPalette(page);
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog", { name: t("palette.title") })).toHaveCount(0);
});

test("JOE : réponse avec sources citées, « la décision reste humaine », aucune donnée médicale", async ({ page }) => {
  await openAs(page, "gestionnaire");
  const { dialog, input } = await openPalette(page);
  await input.fill("Combien de dossiers sont en revue ?");
  await input.press("Enter");
  await expect(dialog.getByTestId("joe-answer-text")).toContainText(REVIEW_CLAIM.claim_number);
  await expect(dialog.getByTestId("joe-sources").getByRole("listitem")).not.toHaveCount(0);
  await expect(dialog.getByTestId("joe-human-decision")).toHaveText(t("joe.humanDecision"));
  for (const medical of MEDICAL) await expect(dialog).not.toContainText(medical);
  await expectNoA11yViolations(page);
  await shot(page, "11-palette-joe-sources");
});

test("médecin-conseil : brouillon de décision affiché comme brouillon, le bouton ouvre le dossier sans l'approuver", async ({ page }) => {
  await openAs(page, "medecin_conseil", `/prises-en-charge?dossier=${REVIEW_CLAIM.id}`);
  const drawer = page.getByRole("dialog", { name: t("claim.drawerLabel", { number: REVIEW_CLAIM.claim_number }) });
  await expect(drawer.getByTestId("claim-status")).toHaveText(t("claimStatus.en_revue"));
  const { dialog } = await openPalette(page);
  await dialog.getByRole("option", { name: t("palette.draft", { number: REVIEW_CLAIM.claim_number }) }).click();
  await expect(dialog.getByTestId("joe-draft-badge")).toHaveText(t("joe.draft.badge"));
  await expect(dialog.getByTestId("joe-draft-recommendation")).toBeVisible();
  await expect(dialog.getByRole("button", { name: t("decision.approve") })).toHaveCount(0);
  await expectNoA11yViolations(page);
  await shot(page, "12-palette-brouillon-decision");
  await dialog.getByRole("button", { name: t("joe.draft.open") }).click();
  await expect(page.getByRole("dialog", { name: t("palette.title") })).toHaveCount(0);
  // Le dossier reste en revue : seul le médecin-conseil décide, depuis le dossier.
  await expect(page.getByTestId("claim-status")).toHaveText(t("claimStatus.en_revue"));
});

test("hors ligne : la palette le dit, JOE est indisponible", async ({ page, context }) => {
  await openAs(page, "gestionnaire");
  await context.setOffline(true);
  const { dialog } = await openPalette(page);
  await expect(dialog.getByTestId("palette-offline")).toContainText(t("palette.offlineCode"));
  await shot(page, "13-palette-hors-ligne");
  await context.setOffline(false);
});

test("états vides guidés : que faire ensuite, avec le geste qui débloque", async ({ page }) => {
  await openAs(page, "gestionnaire", "/prises-en-charge?statut=annulee");
  const empty = page.getByTestId("empty-state");
  await expect(empty).toContainText(t("claims.emptyTitle"));
  await expect(empty.getByTestId("empty-next")).toContainText(t("emptyNext.claimsFilter"));
  await expectNoA11yViolations(page);
  await shot(page, "14-etat-vide-guide-prises-en-charge");
  await empty.getByRole("button", { name: t("emptyNext.showAllClaims") }).click();
  await expect(page.getByRole("table", { name: t("claims.tableLabel") })).toBeVisible();

  await page.goto("/adherents");
  await page.getByLabel(t("members.searchLabel")).fill("zzzz");
  await expect(page.getByTestId("empty-next")).toContainText(t("emptyNext.membersSearch"));
  await page.getByRole("button", { name: t("emptyNext.clearSearch") }).click();
  await expect(page.getByRole("table", { name: t("members.tableLabel") })).toBeVisible();
});

test("Mesure : indicateurs calculés, masqués sous 5 contributeurs ; réservée au gestionnaire", async ({ page }) => {
  await openAs(page, "gestionnaire");
  await page.getByRole("navigation", { name: t("nav.label") }).getByRole("link", { name: t("nav.metrics") }).click();
  await expect(page.getByRole("heading", { level: 1, name: t("metrics.title") })).toBeVisible();
  const table = page.getByRole("table", { name: t("metrics.tableLabel") });
  await expect(table.getByTestId("metric")).toHaveCount(9);
  await expect(table.locator('[data-status="masque"]').first()).toContainText(t("metrics.masked"));
  await expect(table.locator('[data-key="ledger_balance_gap_xof"]')).toContainText(t("metrics.targetMet"));
  await expectNoA11yViolations(page);
  await shot(page, "15-mesure-indicateurs");

  await openAs(page, "medecin_conseil", "/mesure");
  await expect(page.getByText(t("forbidden.gestionnaireOnly"))).toBeVisible();
});

/** Requêtes de mesure envoyées par la page (comptées, corps relus). */
function countTelemetry(page: Page): Record<string, unknown>[] {
  const bodies: Record<string, unknown>[] = [];
  page.on("request", (request) => {
    if (request.method() === "POST" && request.url().endsWith("/v1/telemetry/events")) bodies.push(JSON.parse(request.postData() ?? "{}") as Record<string, unknown>);
  });
  return bodies;
}

/** Gestes mesurés de la console : palette au clavier, question à JOE, palette au bouton. */
async function measuredGestures(page: Page): Promise<void> {
  const { dialog, input } = await openPalette(page);
  await input.fill("Combien de dossiers sont en revue ?");
  await input.press("Enter");
  await expect(dialog.getByTestId("joe-answer-text")).toBeVisible();
  await page.keyboard.press("Escape");
  await page.getByTestId("palette-trigger").click();
  await expect(page.getByRole("dialog", { name: t("palette.title") })).toBeVisible();
  await page.keyboard.press("Escape");
}

test("mesure : sans choix, désactivée ; bandeau sobre de premier usage ; AUCUNE requête de mesure", async ({ page }) => {
  const bodies = countTelemetry(page);
  await openAs(page, "gestionnaire", "/", "unset");
  const banner = page.getByRole("region", { name: t("measure.banner.title") });
  await expect(banner).toContainText(t("measure.banner.text"));
  await expect(page.getByRole("switch", { name: t("measure.switch") })).toHaveAttribute("aria-checked", "false");
  await banner.getByRole("button", { name: t("measure.learnMore") }).click();
  await expect(page.getByTestId("measure-details")).toContainText(t("measure.details.pseudonymous"));
  await expectNoA11yViolations(page);
  await shot(page, "16-mesure-premier-usage");
  await measuredGestures(page);
  await page.waitForTimeout(800);
  expect(bodies).toHaveLength(0);
});

test("mesure : refusée, AUCUNE requête ; le refus survit au rechargement et au changement de profil", async ({ page }) => {
  const bodies = countTelemetry(page);
  await openAs(page, "gestionnaire", "/", "unset");
  await page.getByRole("region", { name: t("measure.banner.title") }).getByRole("button", { name: t("measure.refuse") }).click();
  await expect(page.getByRole("region", { name: t("measure.banner.title") })).toHaveCount(0);
  await measuredGestures(page);
  await page.reload();
  await openAs(page, "medecin_conseil", "/", "unset");
  await expect(page.getByRole("region", { name: t("measure.banner.title") })).toHaveCount(0);
  await expect(page.getByRole("switch", { name: t("measure.switch") })).toHaveAttribute("aria-checked", "false");
  await measuredGestures(page);
  await page.waitForTimeout(800);
  expect(bodies).toHaveLength(0);
  expect(JSON.parse((await page.evaluate((key) => window.localStorage.getItem(key), MEASURE_CHOICE_KEY)) ?? "null")).toEqual({ v: 1, choice: "refused" });
});

test("médecin-conseil : interrupteur dans le menu ; activé, des événements partent ; désactivé, plus aucun", async ({ page }) => {
  const bodies = countTelemetry(page);
  await openAs(page, "medecin_conseil", "/", "unset");
  // Le rôle n'a pas accès à la page « Mesure » : l'interrupteur est dans le menu, pour tous.
  await expect(page.getByRole("navigation", { name: t("nav.label") }).getByRole("link", { name: t("nav.metrics") })).toHaveCount(0);
  const toggle = page.getByRole("complementary").getByRole("switch", { name: t("measure.switch") });
  await expect(toggle).toHaveAttribute("aria-checked", "false");
  await toggle.click();
  await expect(toggle).toHaveAttribute("aria-checked", "true");
  await expect(page.getByRole("region", { name: t("measure.banner.title") })).toHaveCount(0);
  await measuredGestures(page);
  await expect.poll(() => bodies.length).toBeGreaterThan(0);
  expect(bodies.every((b) => b.role === "medecin_conseil" && b.surface === "console")).toBe(true);
  await toggle.click();
  await expect(toggle).toHaveAttribute("aria-checked", "false");
  const before = bodies.length;
  await measuredGestures(page);
  await page.waitForTimeout(800);
  expect(bodies).toHaveLength(before);
});

test("mesure produit (acceptée) : palette ouverte au clavier, question à JOE, jamais le texte de la question", async ({ page }) => {
  const bodies = countTelemetry(page);
  await openAs(page, "gestionnaire", "/", "unset");
  await page.getByRole("region", { name: t("measure.banner.title") }).getByRole("button", { name: t("measure.accept") }).click();
  const { input } = await openPalette(page);
  await input.fill("Combien de dossiers sont en revue ?");
  await input.press("Enter");
  await expect.poll(() => bodies.map((b) => `${String(b.name)}:${String(b.variant)}`)).toEqual(expect.arrayContaining(["palette_opened:clavier", "joe_question_asked:saisie"]));
  for (const body of bodies) {
    expect(Object.keys(body).every((k) => ["name", "surface", "role", "session_id", "duration_ms", "step", "variant"].includes(k))).toBe(true);
    expect(contractProblems(body), JSON.stringify(body)).toEqual([]);
    expect(JSON.stringify(body)).not.toContain("Combien");
  }
});
