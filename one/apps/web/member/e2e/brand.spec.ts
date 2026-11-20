import AxeBuilder from "@axe-core/playwright";
import { expect, test, type BrowserContext, type Page } from "@playwright/test";
import { BRANDING_FIXTURES, BRAND_FIXTURE_COOKIE, CONTRACT_PALETTE } from "../../shared/brand/index";
import { openCard, openPayment, shot } from "./flow";

/**
 * Marque blanche (P3) dans l'espace adhérent : jetons de l'organisation dans le HTML servi (aucun
 * flash), nom et logo sur l'en-tête et la carte, marque « agressive » (échoue AA) repliée sur
 * MulemaCare, lien de paiement public à la marque. Captures : screenshots/brand-*.
 */
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

    const html = await (await context.request.get("/")).text();
    if (brand.applied) {
      expect(html).toContain(`--accent:${fixture.theme.light!.accent}`);
    } else {
      expect(html).not.toContain(`id="mc-brand"`);
    }

    await openCard(page);
    await expect(page.locator("html")).toHaveAttribute("data-brand", brand.applied ? "organisation" : "mulemacare");
    expect(await token(page, "--accent")).toBe(brand.applied ? fixture.theme.light!.accent : CONTRACT_PALETTE.light["--accent"]);
    expect(await token(page, "--brand-deep")).toBe(brand.applied ? fixture.theme.light!.brand_deep : CONTRACT_PALETTE.light["--brand-deep"]);
    expect(await token(page, "--fg")).toBe(CONTRACT_PALETTE.light["--fg"]);

    await expect(page.getByTestId("brand-name")).toHaveText(fixture.display_name);
    await expect(page.getByTestId("member-card")).toContainText(fixture.display_name);
    if (fixture.logo) await expect(page.getByTestId("brand-logo").first()).toHaveAttribute("src", fixture.logo.src);
    else await expect(page.getByTestId("brand-logo")).toHaveCount(0);

    const axe = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"]).analyze();
    expect(axe.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(", ")}`)).toEqual([]);
    await shot(page, `brand-${brand.slug}-clair`);

    await page.emulateMedia({ colorScheme: "dark" });
    expect(await token(page, "--accent")).toBe(brand.applied ? fixture.theme.dark!.accent : CONTRACT_PALETTE.dark["--accent"]);
    const darkAxe = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"]).analyze();
    expect(darkAxe.violations.map((v) => v.id)).toEqual([]);
    await shot(page, `brand-${brand.slug}-sombre`);
  });
}

test("lien de paiement public : à la marque de l'organisation", async ({ page, context, baseURL }) => {
  await chooseOrganization(context, "teranga-assurances", baseURL!);
  await openPayment(page);
  expect(await token(page, "--accent")).toBe(BRANDING_FIXTURES["teranga-assurances"]!.theme.light!.accent);
  await expect(page.locator("header.p-top")).toContainText("Teranga Assurances");
});
