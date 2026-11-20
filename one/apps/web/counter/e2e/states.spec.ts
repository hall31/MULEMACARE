import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import { MockApi } from "./mock-api";
import { fr, openCounter, selectActs, shot, toActs, tr, xof } from "./flow";
import { SCREENS } from "./screens";

/**
 * États du comptoir hors du chemin heureux (contrat de design §8, planche « États ») et captures
 * de la direction « Registre émeraude » : refus R-01, erreur avec code, barème vide puis relancé,
 * chargement, plus la décision en sombre, en plein soleil et aux largeurs 768 et 1280.
 */
const TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"];

async function axeViolations(page: Page): Promise<string[]> {
  const results = await new AxeBuilder({ page }).withTags(TAGS).analyze();
  return results.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(", ")}`);
}

test.describe("états du comptoir", () => {
  test("refus R-01 : cachet barré, règle versionnée, le patient paie le total", async ({ page }) => {
    const api = new MockApi();
    api.memberStatus = "suspendu";
    await openCounter(page, api);
    await toActs(page);
    await selectActs(page, ["CS-GEN", "NFS"]);
    await page.getByRole("button", { name: fr["acts.submit"] }).click();
    await expect(page.getByRole("heading", { level: 1, name: fr["decision.title.refused"] })).toBeVisible();
    await expect(page.getByTestId("verdict").locator('[data-seal="crit"]')).toHaveCount(1);
    await expect(page.getByText(tr("decision.rule", { code: "R-01", version: 1 }))).toBeVisible();
    await expect(page.getByRole("alert").filter({ hasText: "Droits suspendus" })).toBeVisible();
    await expect(page.getByTestId("collect")).toContainText(xof(33_000));
    await expect(page.locator(".who-row .pill")).toHaveText(fr["identity.status.suspendu"]);
    expect(await axeViolations(page)).toEqual([]);
    await shot(page, "09-refus-R-01");
  });

  test("erreur : le message dit quoi faire et porte son code stable", async ({ page }) => {
    await openCounter(page);
    await page.getByLabel(fr["card.numberLabel"]).fill("MC-99999999");
    await page.getByRole("button", { name: fr["card.lookup"] }).click();
    await expect(page.getByTestId("flash")).toContainText("Vérifiez le numéro sur la carte");
    await expect(page.getByTestId("flash")).toContainText(tr("error.codeLabel", { code: "ID-06" }));
    await shot(page, "10-erreur-ID-06");
  });

  test("barème indisponible : état vide avec « Réessayer », puis liste chargée", async ({ page }) => {
    const api = new MockApi();
    api.policyDown = true;
    await openCounter(page, api);
    await toActs(page);
    const empty = page.getByTestId("acts-empty");
    await expect(empty).toContainText(fr["acts.emptyTitle"]);
    await expect(page.getByRole("button", { name: fr["acts.submit"] })).toBeDisabled();
    expect(await axeViolations(page)).toEqual([]);
    await shot(page, "11-bareme-vide");

    api.policyDown = false;
    await empty.getByRole("button", { name: fr["acts.retry"] }).click();
    await expect(page.locator('input[data-act="CS-GEN"]')).toBeVisible();
    await expect(empty).toHaveCount(0);
  });

  test("barème en chargement : squelette après 300 ms, jamais de toupie plein écran", async ({ page }) => {
    const api = new MockApi();
    api.policyDelayMs = 6_000;
    await openCounter(page, api);
    await toActs(page);
    const loading = page.getByTestId("acts-loading");
    await expect(loading).toHaveAttribute("role", "status");
    await expect(loading.locator(".sk").first()).toBeVisible();
    await shot(page, "12-bareme-chargement");
    await expect(page.locator('input[data-act="CS-GEN"]')).toBeVisible({ timeout: 10_000 });
  });

  test("le cachet s'anime une fois (400 ms), et pas du tout en mouvement réduit", async ({ page }) => {
    await SCREENS.decision(page);
    const animation = await page.getByTestId("verdict").locator(".seal").evaluate((el) => {
      const style = getComputedStyle(el);
      return { name: style.animationName, duration: style.animationDuration, count: style.animationIterationCount };
    });
    expect(animation).toEqual({ name: "mc-stamp", duration: "0.4s", count: "1" });
    await page.emulateMedia({ reducedMotion: "reduce" });
    expect(await page.getByTestId("verdict").locator(".seal").evaluate((el) => getComputedStyle(el).animationName)).toBe("none");
  });
});

test.describe("captures de la direction", () => {
  test.describe("sombre", () => {
    test.use({ colorScheme: "dark" });
    test("décision", async ({ page }) => {
      await SCREENS.decision(page);
      await shot(page, "13-decision-sombre");
    });
    test("actes", async ({ page }) => {
      await SCREENS.actes(page);
      await shot(page, "14-actes-sombre");
    });
  });

  test("décision en plein soleil", async ({ page }) => {
    await page.addInitScript(() => window.localStorage.setItem("mulema.sun", "1"));
    await SCREENS.decision(page);
    await expect(page.locator("html")).toHaveAttribute("data-sun", "");
    await shot(page, "15-decision-plein-soleil");
  });

  for (const width of [768, 1280]) {
    test(`décision à ${width} px`, async ({ page }) => {
      await page.setViewportSize({ width, height: 900 });
      await SCREENS.decision(page);
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
      expect(overflow, "débordement horizontal").toBeLessThanOrEqual(0);
      await shot(page, `16-decision-${width}`);
    });
  }

  test("identification hors ligne : bandeau persistant", async ({ page, context }) => {
    const api = await openCounter(page);
    api.networkDown = true;
    await context.setOffline(true);
    await expect(page.getByTestId("offline-banner-title")).toHaveText(tr("net.offline.identification"));
    await shot(page, "17-hors-ligne-carte");
  });
});
