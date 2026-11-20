import { expect, test } from "@playwright/test";
import { axe, openAs } from "./helpers";

/** `make a11y` : axe-core WCAG 2.2 A/AA, espaces assureur et employeur, clair et sombre, 375 et 1280 px. */
for (const scheme of ["light", "dark"] as const) {
  for (const width of [375, 1280]) {
    for (const [role, url, ready] of [["assureur", "/assureur", "portfolio"], ["employeur", "/employeur", "employer-group"]] as const) {
      test(`axe AA — ${role}, ${scheme === "light" ? "clair" : "sombre"}, ${width} px`, async ({ page }) => {
        await page.emulateMedia({ colorScheme: scheme });
        await page.setViewportSize({ width, height: 900 });
        await openAs(page, role, url);
        await expect(page.getByTestId(ready).first()).toBeVisible();
        // Tableaux alternatifs ouverts : audités eux aussi.
        for (const summary of await page.locator("details > summary").all()) await summary.click();
        expect(await axe(page)).toEqual([]);
      });
    }
  }
}
