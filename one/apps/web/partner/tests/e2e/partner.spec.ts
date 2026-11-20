import { readFileSync } from "node:fs";
import { expect, test } from "@playwright/test";
import { t } from "../../src/i18n";
import { axe, openAs, overflow, shot, smallTargets } from "./helpers";

/**
 * Espaces partenaires (P3, voie B) : portefeuille assureur (k-anonymat affiché, tableau
 * alternatif, export CSV agrégé), espace employeur (groupes, échéances), responsive 375 / 768 /
 * 1280 sans débordement, zones de 48 px, axe AA. Captures : screenshots/.
 */
const WIDTHS = [375, 768, 1280] as const;

test("assureur : portefeuille agrégé, masques en clair, tableau alternatif, export CSV", async ({ page }) => {
  await openAs(page, "assureur", "/assureur");
  await expect(page.getByRole("heading", { level: 1, name: t("insurer.title") })).toBeVisible();
  await expect(page.getByTestId("kpi-members")).toContainText(t("kanon.countOpen", { from: 100 }));
  await expect(page.getByTestId("published-period")).toBeVisible();
  await expect(page.getByTestId("chart-statuts").getByTestId("bar-row").filter({ hasText: t("kanon.masked") })).toHaveCount(2);

  await page.getByTestId("chart-categories").getByText(t("chart.showTable")).click();
  await expect(page.getByTestId("chart-categories").getByRole("table")).toBeVisible();

  const download = page.waitForEvent("download");
  await page.getByTestId("export-csv").click();
  const file = await download;
  expect(file.suggestedFilename()).toMatch(/^portefeuille-\d{4}-\d{2}-\d{2}-\d{4}-\d{2}-\d{2}\.csv$/);
  const csv = readFileSync((await file.path())!, "utf8");
  expect(csv.split("\r\n")[0]).toBe("section;cle;statut;valeur;effectif;unite");
  expect(csv).toContain("adherents;suspendu;masque;;;nombre");
  expect(csv).not.toMatch(/;439;/);
  expect(await axe(page)).toEqual([]);
});

test("assureur : semaine dernière seule, valeurs masquées et invitation à élargir", async ({ page }) => {
  await openAs(page, "assureur", "/assureur");
  await page.getByRole("button", { name: t("period.preset.1") }).click();
  await expect(page.getByRole("button", { name: t("period.preset.1") })).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByTestId("masked-note")).toBeVisible();
  await expect(page.getByTestId("chart-categories").getByTestId("bar-row").filter({ hasText: t("categories.autres_regroupes") })).toHaveCount(1);
  await shot(page, "assureur-1-semaine-masques");
  await page.getByRole("button", { name: t("kanon.widen") }).click();
  await expect(page.getByRole("button", { name: t("period.preset.13") })).toHaveAttribute("aria-pressed", "true");
});

test("employeur : groupes anonymisés, petit groupe masqué, contrats arrivant à échéance", async ({ page }) => {
  await openAs(page, "employeur", "/employeur");
  await expect(page.getByRole("heading", { level: 1, name: t("employer.title") })).toBeVisible();
  await expect(page.getByTestId("employer-group")).toHaveCount(2);
  await expect(page.getByTestId("group-masked")).toHaveCount(1);
  await expect(page.getByTestId("contract-row").first()).toHaveAttribute("data-status", "echu");
  await expect(page.getByTestId("contracts-summary")).toHaveText(t("employer.contractsSummary", { count: 1, days: 90 }));
  expect(await axe(page)).toEqual([]);
});

test("l'accueil ouvre l'espace du rôle ; un espace non permis n'est pas affiché", async ({ page }) => {
  await openAs(page, "employeur", "/");
  await expect(page).toHaveURL(/\/employeur$/);
  await expect(page.getByRole("navigation", { name: t("nav.label") }).getByRole("link")).toHaveText([t("nav.employer")]);
});

for (const width of WIDTHS) {
  for (const [role, url] of [["assureur", "/assureur"], ["employeur", "/employeur"]] as const) {
    test(`${role} à ${width} px : aucun débordement, zones de 48 px, clair et sombre`, async ({ page }) => {
      await page.setViewportSize({ width, height: 900 });
      await openAs(page, role, url);
      await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
      await expect(page.getByTestId(role === "assureur" ? "portfolio" : "contracts")).toBeVisible();
      if (role === "employeur") await expect(page.getByTestId("employer-group").first()).toBeVisible();
      expect(await overflow(page)).toBeLessThanOrEqual(0);
      expect(await smallTargets(page)).toEqual([]);
      await shot(page, `${role}-${width}-clair`);
      await page.getByRole("button", { name: t("theme.dark") }).click();
      await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
      expect(await overflow(page)).toBeLessThanOrEqual(0);
      await shot(page, `${role}-${width}-sombre`);
    });
  }
}
