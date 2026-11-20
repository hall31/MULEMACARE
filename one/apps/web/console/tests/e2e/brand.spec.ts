import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import { BRANDING_FIXTURES, BRAND_FIXTURE_COOKIE, CONTRACT_PALETTE } from "../../../shared/brand/index";
import { t } from "../../src/i18n";
import { openAs, shot } from "./helpers";

/**
 * Marque blanche (P3) dans la console : jetons de l'organisation dans le HTML servi (aucun flash),
 * nom, logo et titre de l'onglet à la marque, marque « agressive » (échoue AA) repliée sur
 * MulemaCare, clair et sombre. Captures : screenshots/brand-*.
 */
const BRANDS = [
  { slug: "lagune-sante", applied: true },
  { slug: "teranga-assurances", applied: true },
  { slug: "marque-agressive", applied: false },
] as const;

const token = (page: Page, name: string) => page.evaluate((n) => getComputedStyle(document.documentElement).getPropertyValue(n).trim(), name);

async function axe(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"]).analyze();
  return results.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(", ")}`);
}

for (const brand of BRANDS) {
  test(`marque ${brand.slug} : ${brand.applied ? "appliquée avant le premier rendu" : "repliée sur MulemaCare (contraste)"}`, async ({ page, context, baseURL }) => {
    const fixture = BRANDING_FIXTURES[brand.slug]!;
    await context.addCookies([{ name: BRAND_FIXTURE_COOKIE, value: brand.slug, url: baseURL! }]);
    const html = await (await context.request.get("/")).text();
    if (brand.applied) expect(html).toContain(`--accent:${fixture.theme.light!.accent}`);
    else expect(html).not.toContain(`id="mc-brand"`);
    expect(html).toContain(`<title>${t("app.brandedTitle", { name: fixture.display_name })}</title>`);

    await openAs(page, "gestionnaire");
    await expect(page.locator("html")).toHaveAttribute("data-brand", brand.applied ? "organisation" : "mulemacare");
    expect(await token(page, "--accent")).toBe(brand.applied ? fixture.theme.light!.accent : CONTRACT_PALETTE.light["--accent"]);
    expect(await token(page, "--ok")).toBe(CONTRACT_PALETTE.light["--ok"]);
    await expect(page.getByTestId("brand-name")).toHaveText(fixture.display_name);
    if (fixture.logo) await expect(page.getByTestId("brand-logo")).toHaveAttribute("src", fixture.logo.src);
    else await expect(page.getByTestId("brand-logo")).toHaveCount(0);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    expect(await axe(page)).toEqual([]);
    await shot(page, `brand-${brand.slug}-clair`);

    await page.getByRole("radio", { name: t("theme.dark") }).click();
    await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
    expect(await token(page, "--accent")).toBe(brand.applied ? fixture.theme.dark!.accent : CONTRACT_PALETTE.dark["--accent"]);
    expect(await axe(page)).toEqual([]);
    await shot(page, `brand-${brand.slug}-sombre`);
  });
}
