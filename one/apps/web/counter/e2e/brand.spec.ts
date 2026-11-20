import { readFileSync } from "node:fs";
import AxeBuilder from "@axe-core/playwright";
import { expect, test, type BrowserContext, type Page } from "@playwright/test";
import { BRANDING_FIXTURES, BRAND_FIXTURE_COOKIE, CONTRACT_PALETTE } from "../../shared/brand/index";
import { fr, openCounter, shot } from "./flow";

/**
 * Marque blanche (P3) au comptoir : les jetons de l'organisation sont dans le HTML servi (aucun
 * flash), seuls les jetons de la liste fermée changent, la marque « agressive » (échoue AA) est
 * repliée sur le thème MulemaCare, le plein soleil ignore la marque. Captures : screenshots/brand-*.
 */
const SUN_ACCENT = /\[data-sun\]\s*\{[^}]*--accent:\s*(#[0-9a-f]{6})/.exec(readFileSync("../../../specs/design/mulemacare-tokens.css", "utf8"))?.[1];

const BRANDS = [
  { slug: "lagune-sante", applied: true },
  { slug: "teranga-assurances", applied: true },
  { slug: "marque-agressive", applied: false },
] as const;

async function chooseOrganization(context: BrowserContext, slug: string, baseURL: string): Promise<void> {
  await context.addCookies([{ name: BRAND_FIXTURE_COOKIE, value: slug, url: baseURL }]);
}

const token = (page: Page, name: string) => page.evaluate((n) => getComputedStyle(document.documentElement).getPropertyValue(n).trim(), name);

for (const brand of BRANDS) {
  test(`marque ${brand.slug} : ${brand.applied ? "appliquée avant le premier rendu" : "repliée sur MulemaCare (contraste)"}`, async ({ page, context, baseURL }) => {
    const fixture = BRANDING_FIXTURES[brand.slug]!;
    await chooseOrganization(context, brand.slug, baseURL!);

    // Le HTML servi porte déjà les jetons : aucun rendu intermédiaire au thème MulemaCare.
    const html = await (await context.request.get("/")).text();
    if (brand.applied) {
      expect(html).toContain(`<style id="mc-brand">`);
      expect(html).toContain(`--accent:${fixture.theme.light!.accent}`);
    } else {
      expect(html).not.toContain(`id="mc-brand"`);
    }

    await openCounter(page);
    const root = page.locator("html");
    await expect(root).toHaveAttribute("data-organization", brand.slug);
    await expect(root).toHaveAttribute("data-brand", brand.applied ? "organisation" : "mulemacare");
    expect(await token(page, "--accent")).toBe(brand.applied ? fixture.theme.light!.accent : CONTRACT_PALETTE.light["--accent"]);
    expect(await token(page, "--focus")).toBe(await token(page, "--accent"));
    // Jetons hors liste fermée : jamais touchés.
    expect(await token(page, "--bg")).toBe(CONTRACT_PALETTE.light["--bg"]);
    expect(await token(page, "--ok")).toBe(CONTRACT_PALETTE.light["--ok"]);

    await expect(page.getByTestId("brand-name")).toHaveText(fixture.display_name);
    if (fixture.logo) await expect(page.getByTestId("brand-logo")).toHaveAttribute("src", fixture.logo.src);
    else await expect(page.getByTestId("brand-logo")).toHaveCount(0);

    const axe = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"]).analyze();
    expect(axe.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(", ")}`)).toEqual([]);
    await shot(page, `brand-${brand.slug}-clair`);

    await page.emulateMedia({ colorScheme: "dark" });
    expect(await token(page, "--accent")).toBe(brand.applied ? fixture.theme.dark!.accent : CONTRACT_PALETTE.dark["--accent"]);
    await shot(page, `brand-${brand.slug}-sombre`);

    // Plein soleil : la marque ne s'applique jamais, quel que soit le thème.
    await page.getByRole("button", { name: fr["bar.sun.label"] }).click();
    await expect(root).toHaveAttribute("data-sun", "");
    if (brand.applied) expect(await token(page, "--accent")).not.toBe(fixture.theme.dark!.accent);
    await page.emulateMedia({ colorScheme: "light" });
    expect(await token(page, "--accent")).toBe(SUN_ACCENT);
    await shot(page, `brand-${brand.slug}-plein-soleil`);
  });
}

test("sans organisation : thème MulemaCare, aucun style de marque servi", async ({ page }) => {
  const html = await (await page.request.get("/")).text();
  expect(html).not.toContain(`id="mc-brand"`);
  await openCounter(page);
  await expect(page.locator("html")).toHaveAttribute("data-brand", "mulemacare");
  expect(await token(page, "--accent")).toBe(CONTRACT_PALETTE.light["--accent"]);
});
