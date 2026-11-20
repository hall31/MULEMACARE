import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import { t } from "../../src/i18n";
import { openAs, shot } from "./helpers";

/**
 * Phase 3, voie B — console : « Organisations » (administrateur de plateforme : accueil d'une
 * organisation, ORG-01, gabarits) et « Marque » (administrateur : aperçu en direct, refus BRD-01
 * affiché clairement, couleur conforme la plus proche, enregistrement). axe AA, cibles ≥ 32 px.
 */
// Formulaires longs et axe plusieurs fois par parcours, sur une machine partagée.
test.describe.configure({ timeout: 90_000 });

async function axe(page: Page, exclude: string[] = []) {
  let builder = new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"]);
  for (const selector of exclude) builder = builder.exclude(selector);
  const results = await builder.analyze();
  return results.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(", ")}`);
}

/** Contrôles de la page (hors barre latérale) : 32 px au moins (POLISH_CONTRACT §10, console). */
async function smallTargets(page: Page): Promise<string[]> {
  return page.evaluate(() =>
    [...document.querySelectorAll("main button, main input:not([type=radio]):not([type=checkbox]), main select, main summary, main a")]
      // Champ de fichier masqué (.sr-only) : sa cible est le bouton « Choisir un fichier » (label).
      .filter((el) => (el as HTMLElement).offsetParent !== null && !el.classList.contains("sr-only"))
      .map((el) => ({ el, r: el.getBoundingClientRect() }))
      .filter(({ r }) => r.height < 32)
      .map(({ el, r }) => `${el.tagName.toLowerCase()} ${Math.round(r.height)}px ${(el.textContent ?? "").trim().slice(0, 30)}`),
  );
}

test("plateforme : accueillir une organisation (ORG-01 puis succès), sans violation axe", async ({ page }) => {
  await openAs(page, "admin_plateforme", "/organisations");
  await expect(page.getByRole("heading", { level: 1, name: t("organizations.title") })).toBeVisible();
  await expect(page.getByTestId("template-row").first()).toBeVisible();
  expect(await axe(page)).toEqual([]);
  expect(await smallTargets(page)).toEqual([]);

  await page.getByRole("button", { name: t("organizations.submit") }).click();
  await expect(page.getByTestId("organization-error")).toBeFocused();
  await expect(page.getByLabel(t("organizations.slug"))).toHaveAttribute("aria-invalid", "true");
  expect(await axe(page)).toEqual([]);

  await page.getByLabel(t("organizations.name")).fill("Mutuelle de Bouaké");
  await page.getByLabel(t("organizations.slug")).fill("lagune-sante");
  await page.getByLabel(t("organizations.managerName")).fill("Adjoua Kouamé");
  await page.getByLabel(t("organizations.managerSubject")).fill("idp|bouake-001");
  await page.getByRole("button", { name: t("organizations.submit") }).click();
  await expect(page.getByTestId("organization-error")).toHaveAttribute("data-code", "ORG-01");
  await expect(page.getByTestId("org-slug-erreur")).toBeVisible();
  await shot(page, "20-organisations-org-01");

  await page.getByLabel(t("organizations.slug")).fill("mutuelle-bouake");
  await page.getByRole("button", { name: t("organizations.submit") }).click();
  await expect(page.getByTestId("organization-created")).toContainText(t("organizations.createdProof", { slug: "mutuelle-bouake", code: "mutuelle-ci", version: 2 }));
  await expect(page.getByTestId("onboarded-row")).toHaveCount(1);
  expect(await axe(page)).toEqual([]);
  await shot(page, "21-organisations-accueillie");
});

test("plateforme : accueil sans accès métier (redirigé vers les organisations)", async ({ page }) => {
  await openAs(page, "admin_plateforme");
  await expect(page.getByRole("heading", { level: 1, name: t("home.platformTitle") })).toBeVisible();
  await expect(page.getByRole("navigation", { name: t("nav.label") }).getByRole("link")).toHaveText([t("nav.organizations")]);
});

test("marque : aperçu en direct, refus BRD-01 « contraste insuffisant », couleur conforme proposée, enregistrement", async ({ page }) => {
  await openAs(page, "admin", "/marque");
  await expect(page.getByRole("heading", { level: 1, name: t("branding.title") })).toBeVisible();
  expect(await axe(page)).toEqual([]);
  expect(await smallTargets(page)).toEqual([]);

  const light = page.getByTestId("colors-light");
  const accent = light.getByLabel(t("branding.token.accent"), { exact: true });
  await accent.fill("#ffd400");
  await expect(page.getByTestId("brand-preview-light")).toHaveAttribute("style", /--accent: ?#ffd400/);
  await expect(light.getByTestId("contrast-light")).not.toHaveText(t("branding.contrastOk"));
  await shot(page, "22-marque-apercu-refusable");

  await page.getByRole("button", { name: t("branding.submit") }).click();
  const alert = page.getByTestId("branding-api-error");
  await expect(alert).toHaveAttribute("data-code", "BRD-01");
  await expect(alert).toContainText(t("branding.contrastRefused"));
  await expect(alert).toBeFocused();
  await expect(light.getByTestId("light-accent-erreur")).toContainText("1,43:1");
  // L'aperçu montre volontairement la couleur refusée : il est exclu de l'audit de contraste.
  expect(await axe(page, ['[data-testid^="brand-preview-"]'])).toEqual([]);
  await shot(page, "23-marque-brd-01");

  await light.getByTestId("suggest-light-accent").click();
  await expect(light.getByTestId("contrast-light")).toHaveText(t("branding.contrastOk"));
  const fixed = await accent.inputValue();
  expect(fixed).toMatch(/^#[0-9a-f]{6}$/);
  await page.getByRole("button", { name: t("branding.submit") }).click();
  await expect(page.getByTestId("branding-saved")).toBeVisible();
  expect(await axe(page)).toEqual([]);
  await shot(page, "24-marque-enregistree");
});
