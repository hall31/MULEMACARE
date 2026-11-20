import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import { t } from "../../src/i18n";
import { DEMO_CLAIMS, DEMO_MEMBERS, PLAN_FAMILLE_OR } from "../../src/mocks/fixtures";
import { openAs, shot } from "./helpers";

async function expectNoSeriousA11yViolations(page: Page): Promise<void> {
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
  // Modérées comprises : seules les violations « minor » sont tolérées.
  const serious = results.violations.filter((v) => v.impact === "moderate" || v.impact === "serious" || v.impact === "critical");
  expect(serious.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(", ")}`)).toEqual([]);
}

test("accueil : compteurs « À traiter » issus de l'API, sans chiffre inventé", async ({ page }) => {
  await openAs(page, "gestionnaire");
  const todo = page.getByRole("region", { name: t("home.todoTitle") });
  await expect(todo).toBeVisible();
  const inReview = DEMO_CLAIMS.filter((c) => c.status === "en_revue").length;
  await expect(todo.getByRole("link", { name: new RegExp(t("home.todoReview")) })).toContainText(String(inReview));
  await expect(page.getByRole("region", { name: t("home.recentTitle") }).getByRole("listitem")).not.toHaveCount(0);
  await expectNoSeriousA11yViolations(page);
  await shot(page, "00-accueil-gestionnaire");
});

test("prises en charge : filtre alertes fraude et état vide", async ({ page }) => {
  await openAs(page, "gestionnaire", "/prises-en-charge?fraude=1");
  const table = page.getByRole("table", { name: t("claims.tableLabel") });
  await expect(table.getByRole("row")).toHaveCount(2); // en-tête + 1 dossier signalé
  await expect(table).toContainText(t("fraud.flagged"));
  await expectNoSeriousA11yViolations(page);

  await page.goto("/prises-en-charge?statut=annulee");
  await expect(page.getByText(t("claims.emptyTitle"))).toBeVisible();
});

test("adhérents : recherche, fiche et droits", async ({ page }) => {
  const member = DEMO_MEMBERS[1]!;
  await openAs(page, "gestionnaire");
  await page.getByRole("navigation", { name: t("nav.label") }).getByRole("link", { name: t("nav.members") }).click();
  await expect(page.getByRole("heading", { level: 1, name: t("members.title") })).toBeVisible();

  await page.getByLabel(t("members.searchLabel")).fill(member.holder.family_name);
  const table = page.getByRole("table", { name: t("members.tableLabel") });
  await expect(table.getByRole("row")).toHaveCount(2);
  await table.getByRole("row", { name: new RegExp(member.member_number) }).click();

  const drawer = page.getByRole("dialog", {
    name: t("member.drawerLabel", { name: `${member.holder.given_name} ${member.holder.family_name}` }),
  });
  await expect(drawer).toBeVisible();
  await drawer.getByRole("tab", { name: t("member.tabRights") }).click();
  await expect(drawer.getByText(t("member.rightsOpen"))).toBeVisible();
  await expectNoSeriousA11yViolations(page);
  await shot(page, "06-gestionnaire-fiche-adherent-droits");
});

test("grand livre : lecture seule, balance équilibrée", async ({ page }) => {
  await openAs(page, "gestionnaire", "/grand-livre");
  await expect(page.getByRole("heading", { level: 1, name: t("ledger.title") })).toBeVisible();
  await expect(page.getByText(t("ledger.appendOnly"))).toBeVisible();
  await expect(page.getByTestId("balance-status")).toHaveText(t("ledger.balanced"));
  // Aucune action d'écriture n'est proposée dans la console (lecture seule).
  await expect(page.getByRole("button", { name: /contre-passer/i })).toHaveCount(0);
  await expectNoSeriousA11yViolations(page);
  await shot(page, "07-gestionnaire-grand-livre");
});

test("produits : versions datées et écart avec la version précédente", async ({ page }) => {
  await openAs(page, "gestionnaire", "/produits");
  await expect(page.getByRole("heading", { level: 1, name: t("products.title") })).toBeVisible();
  const versions = page.getByRole("group", { name: t("products.versionsLabel", { name: PLAN_FAMILLE_OR.name }) });
  const current = versions.getByRole("button", { pressed: true });
  await expect(current).toContainText(t("planVersionState.en_vigueur"));

  await versions.getByRole("button", { name: /v3/ }).click();
  await expect(page.getByRole("table", { name: t("products.paramsLabel", { version: 3 }) })).toContainText(
    t("products.colDiff", { version: 2 }),
  );
  await expectNoSeriousA11yViolations(page);
  await shot(page, "08-gestionnaire-produits-versions");
});

test("médecin-conseil : les pages du gestionnaire sont refusées proprement", async ({ page }) => {
  await openAs(page, "medecin_conseil");
  const nav = page.getByRole("navigation", { name: t("nav.label") });
  await expect(nav.getByRole("link", { name: t("nav.members") })).toHaveCount(0);
  await page.goto("/adherents");
  await expect(page.getByText(t("forbidden.gestionnaireOnly"))).toBeVisible();
});

test("focus visible au clavier", async ({ page }) => {
  await openAs(page, "gestionnaire");
  await page.getByRole("link", { name: t("app.skipToContent") }).focus();
  await page.keyboard.press("Tab");
  const focused = page.locator(":focus");
  const outline = await focused.evaluate((el) => getComputedStyle(el).outlineStyle);
  expect(outline).not.toBe("none");
});

test("prefers-reduced-motion : le tiroir s'ouvre sans animation", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await openAs(page, "gestionnaire", "/prises-en-charge");
  await page.getByRole("table", { name: t("claims.tableLabel") }).getByRole("row").nth(1).click();
  const drawer = page.getByRole("dialog");
  await expect(drawer).toBeVisible();
  const duration = await drawer.evaluate((el) => getComputedStyle(el).animationDuration);
  expect(["0s", "1e-05s", "0.00001s"]).toContain(duration);
});

test("mode sombre (jetons sombres du contrat) : contraste AA", async ({ page }) => {
  await page.emulateMedia({ colorScheme: "dark" });
  await openAs(page, "medecin_conseil", "/prises-en-charge?statut=en_revue");
  await expect(page.getByRole("table", { name: t("claims.tableLabel") })).toBeVisible();
  await expectNoSeriousA11yViolations(page);
  await shot(page, "09-mode-sombre-prises-en-charge");
});
