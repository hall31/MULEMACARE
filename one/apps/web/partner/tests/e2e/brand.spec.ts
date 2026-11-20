import { expect, test, type Page } from "@playwright/test";
import { BRANDING_FIXTURES, BRAND_FIXTURE_COOKIE, CONTRACT_PALETTE } from "../../../shared/brand/index";
import { t } from "../../src/i18n";
import { axe, openAs, shot } from "./helpers";

/** Marque blanche (P3) dans les espaces partenaires : appliquée avant le premier rendu, ou repliée (AA). */
const BRANDS = [
  { slug: "lagune-sante", applied: true },
  { slug: "teranga-assurances", applied: true },
  { slug: "marque-agressive", applied: false },
] as const;
const token = (page: Page, name: string) => page.evaluate((n) => getComputedStyle(document.documentElement).getPropertyValue(n).trim(), name);

for (const brand of BRANDS) {
  test(`marque ${brand.slug}`, async ({ page, context, baseURL }) => {
    const fixture = BRANDING_FIXTURES[brand.slug]!;
    await context.addCookies([{ name: BRAND_FIXTURE_COOKIE, value: brand.slug, url: baseURL! }]);
    const html = await (await context.request.get("/assureur")).text();
    if (brand.applied) expect(html).toContain(`--accent:${fixture.theme.light!.accent}`);
    else expect(html).not.toContain(`id="mc-brand"`);
    await openAs(page, "assureur", "/assureur");
    await expect(page.getByTestId("portfolio")).toBeVisible();
    expect(await token(page, "--accent")).toBe(brand.applied ? fixture.theme.light!.accent : CONTRACT_PALETTE.light["--accent"]);
    expect(await token(page, "--ok")).toBe(CONTRACT_PALETTE.light["--ok"]);
    await expect(page.getByTestId("brand-name")).toHaveText(fixture.display_name);
    expect(await axe(page)).toEqual([]);
    await shot(page, `brand-${brand.slug}-clair`);
    await page.getByRole("button", { name: t("theme.dark") }).click();
    expect(await token(page, "--accent")).toBe(brand.applied ? fixture.theme.dark!.accent : CONTRACT_PALETTE.dark["--accent"]);
    expect(await axe(page)).toEqual([]);
    await shot(page, `brand-${brand.slug}-sombre`);
  });
}
